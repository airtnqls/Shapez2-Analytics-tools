import { solveRank0PinPush } from "../lib/raw-pinpush-rank0";
import { parseCode, rowsToCode } from "../lib/shape";
import { pushPin } from "../lib/physics";

const TARGET = "SS--:SS--:-S--:SS--:-S--:cS--:SS--:-S--:SS--:-S--:cS--";
const CAP = 11;

const started = performance.now();
const result = solveRank0PinPush(parseCode(TARGET, CAP), CAP, {
  transitionLimit: 25_000_000,
});
const elapsedMs = performance.now() - started;
let replay: string | null = null;
let replayOk = false;
if (result.ok && result.predecessor !== undefined) {
  replay = rowsToCode(pushPin(parseCode(result.predecessor, CAP), CAP));
  replayOk = replay === TARGET;
}
console.log(JSON.stringify({ target: TARGET, cap: CAP, elapsedMs, result, replay, replayOk }, null, 2));
