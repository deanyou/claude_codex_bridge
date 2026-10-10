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
import { createSession } from "@earendil-works/pi-durable";
import readline from "node:readline";

const ctx = BACKGROUND_CONTEXT;

// ---- in-process caches ----
/** @type {Map<string, {storage: any, session: any}>} key=absolute storage path */
const storageCache = new Map();
/** @type {Map<string, {storagePath: string, conversationId: string}>} key=handleId */
const handles = new Map();
/** @type {Set<string>} process-local registered conversations */
const registeredConversations = new Set();

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

function submissionToState(sub) {
  // pi-durable SubmissionRecord shape depends on (type, status).
  // For our path we always create {type:"input", status:"unanswered", reason:inputText}.
  // Map back to SubmissionState for Python.  All IDs are normalized to strings
  // because pi-durable's branded nominal IDs are runtime numbers, but Python
  // (and JSON transit) are easier when opaque IDs stay strings end-to-end.
  const text = (sub && sub.reason) || "";
  return {
    submission_id: String(sub.id),
    conversation_id: String(sub.conversationId),
    request_id: sub.requestId || "",
    input_hash: "",  // Worker doesn't track hash; Python computes from input_text
    status: "settled",
    text,
    finish_reason: "replayed",
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
  const { handleId, conversationId, requestId, inputText } = params;
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
  // idempotency check
  const existing = await session.commit(
    (tx) => tx.submissionByRequest(conversationId, requestId),
    ctx
  );
  if (existing) {
    const prev = existing.reason || "";
    if (prev !== inputText) {
      throw {
        kind: "backend_error",
        message: `requestId reused with different input (existing=${prev.slice(0,40)}... new=${inputText.slice(0,40)}...)`,
      };
    }
    return submissionToState(existing);
  }
  // create new — status "unanswered" with reason=inputText so the text is
  // available for input-comparison on subsequent submissions after reopen.
  const sub = await session.commit(
    (tx) =>
      tx.createSubmission({
        conversationId,
        requestId,
        type: "input",
        status: "unanswered",
        reason: inputText,
      }),
    ctx
  );
  return submissionToState(sub);
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
