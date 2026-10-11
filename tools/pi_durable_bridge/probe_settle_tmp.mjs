import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";
import { openNodeSqliteStorage } from "@earendil-works/pi-durable/storage/sqlite/node";
import { createSession } from "@earendil-works/pi-durable";
import fs from "node:fs"; import os from "node:os"; import path from "node:path";
const ctx = BACKGROUND_CONTEXT;
const tmp = path.join(os.tmpdir(), `settle-probe-${process.pid}.sqlite`);
if (fs.existsSync(tmp)) fs.unlinkSync(tmp);
const storage = await openNodeSqliteStorage(tmp);
const session = createSession(storage);
const say = (m) => console.log(m);

// 建一个 conversation
const conv = await session.commit((tx) => tx.createConversation({ ownership: { kind: "ownerless" } }), ctx);
say("[1] conversation id = " + conv.id);

// A. 原生 queued 状态能不能建（不夹带 input 文本）
const q = await session.commit((tx) =>
  tx.createSubmission({ conversationId: String(conv.id), requestId: "r-q", type: "input", status: "queued" }), ctx)
  .catch(e => ({ ERROR: String(e) }));
say("[A] createSubmission(status:'queued') -> " + JSON.stringify(q));

// B. settleSubmission 能不能把 queued 转 done
try {
  await session.commit((tx) => {
    tx.settleSubmission(q.id, { status: "done", answer: "entry-1" });
  }, ctx);
  const after = await session.commit((tx) => tx.submission(q.id), ctx);
  say("[B] settleSubmission(status:'done', answer:'entry-1') -> OK, now = " + JSON.stringify(after));
} catch (e) {
  say("[B] settleSubmission FAILED -> " + String(e));
}

// C. settleSubmission 转 unanswered（interrupted 语义）
const q2 = await session.commit((tx) =>
  tx.createSubmission({ conversationId: String(conv.id), requestId: "r-u", type: "input", status: "queued" }), ctx)
  .catch(e => ({ ERROR: String(e) }));
try {
  await session.commit((tx) => {
    tx.settleSubmission(q2.id, { status: "unanswered", reason: "process_died" });
  }, ctx);
  const after2 = await session.commit((tx) => tx.submission(q2.id), ctx);
  say("[C] settleSubmission(status:'unanswered', reason) -> OK, now = " + JSON.stringify(after2));
} catch (e) {
  say("[C] settleSubmission FAILED -> " + String(e));
}

// D. detail 字段能不能放 input 文本
try {
  const q3 = await session.commit((tx) =>
    tx.createSubmission({ conversationId: String(conv.id), requestId: "r-d", type: "input", status: "queued" }), ctx);
  await session.commit((tx) => {
    tx.settleSubmission(q3.id, { status: "unanswered", reason: "interrupted", detail: { inputText: "hello world" } });
  }, ctx);
  const after3 = await session.commit((tx) => tx.submission(q3.id), ctx);
  say("[D] detail 夹带 inputText -> " + JSON.stringify(after3));
} catch (e) {
  say("[D] detail FAILED -> " + String(e));
}
