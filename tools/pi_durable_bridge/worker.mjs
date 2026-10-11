// pi-durable worker (Step 2 bridge)
//
// Architecture:
//   stdin  ← JSON-lines request {"id":N,"method":"...","params":{...}}
//   stdout → JSON-lines response {"id":N,"ok":true,"result":{...}} or
//                              {"id":N,"ok":false,"errorKind":"...","message":"..."}
//   stderr → debug / log lines (Python side captures at logger.debug)
//
// Context construction:
//   We use BACKGROUND_CONTEXT from @earendil-works/chord/context. The README
//   confirms this is the canonical "never cancel" context.  All pi-durable
//   Storage / Tx / Session methods either ignore context (underscored param
//   in storage.js) or pass it along; none of our operations need cancellation.
//
// Routes chosen:
//   We do NOT use Harness.open — that path requires a real `models` and
//   `registry` from @earendil-works/pi-ai.  We don't need a model: the
//   DurableBackend Protocol only needs (conversation_id, requestId)
//   idempotency on the storage level.  So we use SqliteStorage +
//   createSession directly:
//
//     open(path, conv_id?):
//       - conv_id empty/null → create new conv (persist in SQLite)
//       - conv_id given      → lookup via tx.conversation; undefined → BackendNotFound
//                              (also accept conv_id from in-process register)
//     submit(...):
//       - idem check: tx.submissionByRequest(convId, reqId)
//       - if found: compare input_text against sub.reason; mismatch → error
//       - else: createSubmission({...status:"unanswered", reason: inputText})
//               (we use "unanswered" with reason=inputText to keep a
//                textual record of what was submitted, satisfying the
//                same-input hash comparison after reopen)
//     status(id): tx.submission(submissionId)
//     close(handle): just drop from handles map; storage untouched
//     register_conversation: in-memory Set (process-local)
//     list_conversations: union(register set, scanConversations per cached storage)

import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";
import { openNodeSqliteStorage } from "@earendil-works/pi-durable/storage/sqlite/node";
import { createSession, UserEntry, AssistantEntry } from "@earendil-works/pi-durable";
import readline from "node:readline";

const ctx = BACKGROUND_CONTEXT;

// ---- in-process caches ----
/** @type {Map<string, {storage: any, session: any}>} key=absolute storage path */
const storageCache = new Map();
/** @type {Map<string, {storagePath: string, conversationId: string}>} key=handleId */
const handles = new Map();
/** @type {Set<string>} process-local registered conversations */
const registeredConversations = new Set();
/** @type {Map<string, any>} dispatch_key -> submissionId（进程内去重）*/
const dispatchKeyIndex = new Map();

// ---- helpers ----
let nextHandleSerial = 1;
function freshHandleId() {
  nextHandleSerial += 1;
  return `h-${Date.now().toString(36)}-${nextHandleSerial.toString(36)}`;
}

async function getStorageSession(storagePath) {
  let entry = storageCache.get(storagePath);
  if (entry) return entry;
  const storage = await openNodeSqliteStorage(storagePath);
  const session = createSession(storage);
  entry = { storage, session };
  storageCache.set(storagePath, entry);
  return entry;
}

async function findConversation(storagePath, conversationId) {
  const { session } = await getStorageSession(storagePath);
  return await session.commit((tx) => tx.conversation(conversationId), ctx);
}

async function createConversation(storagePath) {
  const { session } = await getStorageSession(storagePath);
  // createConversation returns ConversationRecord = { id, parent?, owner? }
  const rec = await session.commit(
    (tx) => tx.createConversation({ ownership: { kind: "ownerless" } }),
    ctx
  );
  return String(rec.id);
}

/** pi-durable 原生状态 -> 我们的三态。 */
function nativeStatusToOurs(sub) {
  const st = sub && sub.status;
  switch (st) {
    // 已受理，尚未进 transcript —— 什么都没发生
    case "queued":
      return { status: "pending", finish_reason: "queued" };
    // 已进 transcript，被活跃 run 拥有 —— 执行中
    case "placed":
      return { status: "pending", finish_reason: "placed" };
    // 已回答
    case "done":
      return { status: "settled", finish_reason: "answered" };
    // 终态但无答案
    case "unanswered": {
      const reason = (sub && sub.reason) || "";
      // reason 带我们的标记前缀 => 显式标记的 interrupted
      if (reason.startsWith("interrupted:")) {
        return { status: "interrupted", finish_reason: reason.slice("interrupted:".length) || "unknown" };
      }
      return { status: "interrupted", finish_reason: reason || "unanswered" };
    }
    default:
      return { status: "pending", finish_reason: String(st || "unknown") };
  }
}

/** 从 record 里取回 input 文本（不再靠塞 reason 字段）。 */
function inputTextOf(sub) {
  if (!sub) return "";
  const d = sub.detail;
  if (d && typeof d === "object" && typeof d.inputText === "string") return d.inputText;
  return "";
}

function submissionToState(sub) {
  // 如实映射 pi-durable 原生状态，不再硬编码 settled/replayed。
  // All IDs are normalized to strings because pi-durable's branded nominal IDs
  // are runtime numbers, but Python (and JSON transit) prefer strings end-to-end.
  const m = nativeStatusToOurs(sub);
  return {
    submission_id: String(sub.id),
    conversation_id: String(sub.conversationId),
    request_id: sub.requestId || "",
    input_hash: "",  // Worker doesn't track hash; Python computes from input_text
    status: m.status,
    finish_reason: m.finish_reason,
    text: inputTextOf(sub),
    entry_id: sub.entry ? String(sub.entry) : null,
    answer_entry_id: sub.answer ? String(sub.answer) : null,
    dispatch_key: (sub.detail && typeof sub.detail === "object" && typeof sub.detail.dispatchKey === "string")
      ? sub.detail.dispatchKey : null,
  };
}

// ---- IPC plumbing ----
function reply(id, ok, payload) {
  const obj = ok
    ? { id, ok: true, result: payload }
    : { id, ok: false, errorKind: payload.errorKind, message: payload.message };
  process.stdout.write(JSON.stringify(obj) + "\n");
}

function reject(id, errorKind, message) {
  console.error(`[worker] rejecting id=${id} ${errorKind}: ${message}`);
  reply(id, false, { errorKind, message });
}

// ---- method dispatch ----
async function handleOpen(params) {
  const storagePath = params.storagePath;
  let conversationId = params.conversationId;

  // validate storagePath
  if (typeof storagePath !== "string" || storagePath.length === 0) {
    throw { kind: "backend_error", message: "storage_path must be a non-empty string" };
  }

  // two branches: existing conv vs new conv
  const wantExisting = conversationId !== null && conversationId !== undefined && conversationId !== "";
  if (wantExisting) {
    if (typeof conversationId !== "string") {
      throw { kind: "backend_error", message: "conversation_id must be a string" };
    }
    if (!registeredConversations.has(conversationId)) {
      const conv = await findConversation(storagePath, conversationId);
      if (!conv) {
        throw { kind: "backend_not_found", message: `conversation not found: ${conversationId}` };
      }
    }
  } else {
    conversationId = await createConversation(storagePath);
  }

  const handleId = freshHandleId();
  // conversation ids are normalized to strings so Python can rely on string identity
  handles.set(handleId, { storagePath, conversationId: String(conversationId) });
  return {
    handle_id: handleId,
    storage_path: storagePath,
    conversation_id: conversationId,
  };
}

async function handleSubmit(params) {
  const { handleId, conversationId, requestId, inputText, dispatchKey } = params;
  if (typeof handleId !== "string" || !handleId) {
    throw { kind: "backend_error", message: "handleId required" };
  }
  const h = handles.get(handleId);
  if (!h) {
    throw { kind: "backend_not_found", message: `unknown handle_id: ${handleId}` };
  }
  if (typeof requestId !== "string" || !requestId) {
    throw { kind: "backend_error", message: "request_id must be a non-empty string" };
  }
  if (typeof inputText !== "string") {
    throw { kind: "backend_error", message: "input_text must be a string" };
  }
  if (String(conversationId) !== String(h.conversationId)) {
    throw {
      kind: "invalid_state",
      message: `conversation mismatch: handle=${h.conversationId} requested=${conversationId}`,
    };
  }
  const { session } = await getStorageSession(h.storagePath);

  // dispatch_key 幂等优先于 requestId 幂等 ——
  // 提案里 dispatch_key 是工具派发的独立幂等键，与请求幂等不是一回事。
  // tx 层只有 submissionByRequest，没有 scan submissions，所以用进程内索引
  // （键为 `${conversationId}\u0000${dispatchKey}`）。跨进程重启后
  // requestId 路径仍然兜底，dispatch_key 只保证同进程内不产生第二次副作用。
  if (typeof dispatchKey === "string" && dispatchKey) {
    const dkKey = conversationId + "\u0000" + dispatchKey;
    const cachedId = dispatchKeyIndex.get(dkKey);
    if (cachedId) {
      const cached = await session.commit((tx) => tx.submission(cachedId), ctx);
      if (cached) return submissionToState(cached);
    }
  }

  // requestId 幂等：tx.createSubmission 本身**不**去重（实测同 requestId 会建第二条），
  // 幂等只在 root.submit() 层。这里必须自己先查。
  const existing = await session.commit(
    (tx) => tx.submissionByRequest(conversationId, requestId),
    ctx
  );
  if (existing) {
    const prev = inputTextOf(existing);
    if (prev !== inputText) {
      throw {
        kind: "backend_error",
        message: `requestId reused with different input (existing=${prev.slice(0,40)}... new=${inputText.slice(0,40)}...)`,
      };
    }
    return submissionToState(existing);
  }

  // 原生 queued：已受理、未进 transcript，如实反映"什么都没发生"。
  // inputText 放 detail.inputText（结构化字段），**不再**塞进 status/reason。
  const detail = { inputText };
  if (typeof dispatchKey === "string" && dispatchKey) detail.dispatchKey = dispatchKey;
  const sub = await session.commit(
    (tx) =>
      tx.createSubmission({
        conversationId,
        requestId,
        type: "input",
        status: "queued",
        detail,
      }),
    ctx
  );
  if (typeof dispatchKey === "string" && dispatchKey) {
    dispatchKeyIndex.set(conversationId + "\u0000" + dispatchKey, sub.id);
  }
  return submissionToState(sub);
}

/** 显式结算为 done：queued -> placeSubmission -> settleSubmission(done)。 */
async function handleSettle(params) {
  const { handleId, conversationId, submissionId, answerText } = params;
  const h = handles.get(handleId);
  if (!h) throw { kind: "backend_not_found", message: `unknown handle_id: ${handleId}` };
  if (String(conversationId) !== String(h.conversationId)) {
    throw { kind: "invalid_state", message: "conversation mismatch" };
  }
  if (typeof answerText !== "string" || !answerText) {
    throw { kind: "backend_error", message: "answer_text must be a non-empty string" };
  }
  const { session } = await getStorageSession(h.storagePath);
  const sub = await session.commit((tx) => tx.submission(submissionId), ctx);
  if (!sub) throw { kind: "backend_not_found", message: `unknown submission: ${submissionId}` };

  // queued 必须先 place 到一个 entry 才能 settle 为 done
  let entryId = sub.entry ? String(sub.entry) : null;
  if (!entryId) {
    const e = await session.commit(
      (tx) => tx.appendEntry(UserEntry, conversationId, { data: { inputText: inputTextOf(sub) } }),
      ctx
    );
    entryId = String(e.id);
    await session.commit((tx) => tx.placeSubmission(submissionId, entryId), ctx);
  }
  const answer = await session.commit(
    (tx) => tx.appendEntry(AssistantEntry, conversationId, { data: { text: answerText } }),
    ctx
  );
  await session.commit(
    (tx) => tx.settleSubmission(submissionId, { status: "done", answer: String(answer.id) }),
    ctx
  );
  const after = await session.commit((tx) => tx.submission(submissionId), ctx);
  return submissionToState(after);
}

/** 显式标记 interrupted（进程死亡时未完成）。 */
async function handleMarkInterrupted(params) {
  const { handleId, conversationId, submissionId, reason } = params;
  const h = handles.get(handleId);
  if (!h) throw { kind: "backend_not_found", message: `unknown handle_id: ${handleId}` };
  if (String(conversationId) !== String(h.conversationId)) {
    throw { kind: "invalid_state", message: "conversation mismatch" };
  }
  const why = typeof reason === "string" && reason ? reason : "process_died";
  const { session } = await getStorageSession(h.storagePath);
  const sub = await session.commit((tx) => tx.submission(submissionId), ctx);
  if (!sub) throw { kind: "backend_not_found", message: `unknown submission: ${submissionId}` };
  if (sub.status === "done") {
    throw { kind: "invalid_state", message: "submission already done; cannot mark interrupted" };
  }
  await session.commit(
    (tx) => tx.settleSubmission(submissionId, { status: "unanswered", reason: "interrupted:" + why }),
    ctx
  );
  const after = await session.commit((tx) => tx.submission(submissionId), ctx);
  return submissionToState(after);
}

async function handleStatus(params) {
  const { handleId, submissionId } = params;
  if (typeof submissionId !== "string" || !submissionId) {
    throw { kind: "backend_error", message: "submissionId required" };
  }
  const h = handles.get(handleId);
  if (!h) {
    throw { kind: "backend_not_found", message: `unknown handle_id: ${handleId}` };
  }
  const { session } = await getStorageSession(h.storagePath);
  const sub = await session.commit((tx) => tx.submission(submissionId), ctx);
  if (!sub) {
    throw { kind: "backend_not_found", message: `unknown submission_id: ${submissionId}` };
  }
  return submissionToState(sub);
}

function handleClose(params) {
  const { handleId } = params;
  if (typeof handleId !== "string" || !handleId) {
    throw { kind: "backend_error", message: "handleId required" };
  }
  handles.delete(handleId);  // storage untouched (matches InMemoryDurableBackend.close)
  return { closed: true };
}

function handleRegister(params) {
  const { conversationId } = params;
  if (typeof conversationId !== "string" || !conversationId) {
    throw { kind: "backend_error", message: "conversationId must be non-empty string" };
  }
  registeredConversations.add(conversationId);
  return { registered: true };
}

async function handleListConversations(params) {
  // storagePath 是可选的，但**重启后重建索引必须传**：
  // storageCache 是进程本地的，桥重启后为空，不给路径就无从扫描，
  // list_conversations 会返回 []，索引重建就失效了。
  const requested = params && params.storagePath;
  const out = new Set(registeredConversations);

  const paths = new Set(storageCache.keys());
  if (typeof requested === "string" && requested.length > 0) paths.add(requested);

  for (const path of paths) {
    try {
      // getStorageSession 会在未缓存时打开并缓存（重启后的首次调用走这里）
      const { session } = await getStorageSession(path);
      const page = await session.commit((tx) => tx.scanConversations({}, 10000), ctx);
      for (const c of page.items) out.add(String(c.id));
    } catch (err) {
      console.error(`[worker] scanConversations failed for ${path}: ${err && err.message || err}`);
    }
  }
  return { conversations: [...out].sort() };
}

async function handleShutdown() {
  for (const [, { storage }] of storageCache.entries()) {
    try {
      await storage.close(ctx);
    } catch (err) {
      console.error(`[worker] storage.close failed: ${err && err.message || err}`);
    }
  }
  process.stdout.write(JSON.stringify({ id: null, ok: true, result: { shutdown: true } }) + "\n");
  setImmediate(() => process.exit(0));
  return null;  // signal "already replied" to outer loop
}

async function dispatchMethod(method, params) {
  switch (method) {
    case "open":                  return await handleOpen(params);
    case "submit":                return await handleSubmit(params);
    case "status":                return await handleStatus(params);
    case "close":                 return handleClose(params);
    case "register_conversation": return handleRegister(params);
    case "list_conversations":    return await handleListConversations(params || {});
    case "settle":                return await handleSettle(params);
    case "mark_interrupted":      return await handleMarkInterrupted(params);
    case "shutdown":              return await handleShutdown();
    case "ping":                  return { pong: true };
    default: throw { kind: "rpc_error", message: `unknown method: ${method}` };
  }
}

// ---- main loop ----
const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
console.error("[worker] ready, pid=" + process.pid);
process.stdout.write(JSON.stringify({ id: null, ok: true, result: { ready: true, pid: process.pid } }) + "\n");

rl.on("line", async (line) => {
  if (!line.trim()) return;
  let req;
  try {
    req = JSON.parse(line);
  } catch (err) {
    console.error(`[worker] JSON parse error: ${err && err.message || err}`);
    process.stdout.write(JSON.stringify({
      id: null, ok: false, errorKind: "rpc_error",
      message: "request not valid json: " + (err && err.message || String(err)),
    }) + "\n");
    return;
  }
  const id = req.id ?? null;
  const method = req.method;
  const params = req.params || {};
  try {
    const result = await dispatchMethod(method, params);
    if (method !== "shutdown") {
      reply(id, true, result);
    }
  } catch (errOrObj) {
    let kind = "rpc_error";
    let message = String((errOrObj && errOrObj.message) || errOrObj);
    if (errOrObj && typeof errOrObj === "object" && "kind" in errOrObj) {
      kind = errOrObj.kind;
      message = errOrObj.message || message;
    }
    reject(id, kind, message);
  }
});

rl.on("close", () => {
  console.error("[worker] stdin closed, exiting");
  setImmediate(() => process.exit(0));
});

process.on("uncaughtException", (err) => {
  console.error("[worker] uncaughtException:", err && err.stack || err);
});
process.on("unhandledRejection", (err) => {
  console.error("[worker] unhandledRejection:", err && err.stack || err);
});
