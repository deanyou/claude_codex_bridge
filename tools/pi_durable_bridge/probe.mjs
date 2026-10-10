// Probe — verify @earendil-works/pi-durable + chord API works end-to-end
import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";
import { openNodeSqliteStorage } from "@earendil-works/pi-durable/storage/sqlite/node";
import { createSession } from "@earendil-works/pi-durable";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const ctx = BACKGROUND_CONTEXT;
const tmp = path.join(os.tmpdir(), `pi-probe-${process.pid}-${Date.now()}.sqlite`);
console.log("probe PID:", process.pid);
console.log("probe temp sqlite:", tmp);
if (fs.existsSync(tmp)) fs.unlinkSync(tmp);

const storage = await openNodeSqliteStorage(tmp);
const session = createSession(storage);
console.log("[1] openNodeSqliteStorage + createSession OK");

// session.commit signature is (change, context), NOT (context, change)!
const newConv = await session.commit((tx) =>
  tx.createConversation({ ownership: { kind: "ownerless" } }), ctx);
console.log("[2] newConv.id =", newConv.id);
console.log("    keys:", Object.keys(newConv).join(","));

const found = await session.commit((tx) => tx.conversation(newConv.id), ctx);
console.log("[3] found.id =", found?.id, "match=", found?.id === newConv.id);

const missing = await session.commit((tx) => tx.conversation("never-existed-asf"), ctx);
console.log("[4] missing =", missing);

const scan = await session.commit((tx) => tx.scanConversations({}, 100), ctx);
console.log("[5] scanConversations found", scan.items.length, "items");
for (const c of scan.items) console.log("    -", c.id);

const sub = await session.commit((tx) =>
  tx.createSubmission({
    conversationId: newConv.id,
    requestId: "probe-req-1",
    type: "input",
    status: "queued",
  }), ctx);
console.log("[6] sub.id =", sub.id, "status=", sub.status, "type=", sub.type);

const dup = await session.commit((tx) =>
  tx.submissionByRequest(newConv.id, "probe-req-1"), ctx);
console.log("[7] dup.id =", dup?.id, "match=", dup?.id === sub.id);

const s2 = await session.commit((tx) => tx.submission(sub.id), ctx);
console.log("[8] s2.id =", s2?.id, "requestId=", s2?.requestId);

// Reopen
await storage.close(ctx);
const storage2 = await openNodeSqliteStorage(tmp);
const session2 = createSession(storage2);
const stillConv = await session2.commit((tx) => tx.conversation(newConv.id), ctx);
const stillSub = await session2.commit((tx) => tx.submissionByRequest(newConv.id, "probe-req-1"), ctx);
console.log("[9] conv still there:", stillConv?.id, "match=", stillConv?.id === newConv.id);
console.log("    sub still there:", stillSub?.id, "match=", stillSub?.id === sub.id);

await storage2.close(ctx);
try { fs.unlinkSync(tmp); } catch {}
console.log("PROBE_OK");
