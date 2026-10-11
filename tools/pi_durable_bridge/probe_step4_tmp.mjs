import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";
import { openNodeSqliteStorage } from "@earendil-works/pi-durable/storage/sqlite/node";
import { createSession, UserEntry, AssistantEntry } from "@earendil-works/pi-durable";
import fs from "node:fs"; import os from "node:os"; import path from "node:path";
const ctx = BACKGROUND_CONTEXT;
const tmp = path.join(os.tmpdir(), `p4-${process.pid}.sqlite`);
if (fs.existsSync(tmp)) fs.unlinkSync(tmp);
const session = createSession(await openNodeSqliteStorage(tmp));
const say = (m) => console.log(m);

const conv = await session.commit((tx) => tx.createConversation({ ownership: { kind: "ownerless" } }), ctx);
const cid = String(conv.id);
say("[1] conversation " + cid);

const sub = await session.commit((tx) =>
  tx.createSubmission({ conversationId: cid, requestId: "r1", type: "input", status: "queued" }), ctx);
say("[2] queued sub id=" + sub.id + " status=" + sub.status);

// 三参重载：appendEntry(UserEntry, cid, draft)
let entryId;
try {
  const e = await session.commit((tx) =>
    tx.appendEntry(UserEntry, cid, { data: { text: "probe-input" } }), ctx);
  entryId = e.id;
  say("[3] appendEntry(UserEntry,cid,draft) OK id=" + entryId + " kind=" + e.kind);
} catch (e) {
  say("[3] FAILED -> " + String(e).slice(0,220));
  process.exit(0);
}

try {
  await session.commit((tx) => tx.placeSubmission(sub.id, entryId), ctx);
  const p = await session.commit((tx) => tx.submission(sub.id), ctx);
  say("[4] placeSubmission OK -> status=" + p.status + " entry=" + p.entry);
} catch (e) {
  say("[4] placeSubmission FAILED -> " + String(e).slice(0,220));
}

try {
  const ans = await session.commit((tx) =>
    tx.appendEntry(AssistantEntry, cid, { data: { text: "probe-answer" } }), ctx);
  await session.commit((tx) => tx.settleSubmission(sub.id, { status: "done", answer: ans.id }), ctx);
  const d = await session.commit((tx) => tx.submission(sub.id), ctx);
  say("[5] settleSubmission(done) OK -> status=" + d.status + " answer=" + d.answer);
} catch (e) {
  say("[5] settleSubmission(done) FAILED -> " + String(e).slice(0,220));
}

try {
  const dup = await session.commit((tx) =>
    tx.createSubmission({ conversationId: cid, requestId: "r1", type: "input", status: "queued" }), ctx);
  say("[6] 重复 requestId -> id=" + dup.id + (dup.id === sub.id ? " 幂等OK" : " !!! 建了新 submission"));
} catch (e) {
  say("[6] 重复 requestId 被拒 -> " + String(e).slice(0,180));
}
