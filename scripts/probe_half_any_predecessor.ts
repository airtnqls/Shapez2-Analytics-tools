import { isRank0Code, solveAnyPinPush } from "../lib/raw-pinpush-rank0";
import { parseCode, rowsToCode } from "../lib/shape";
import { pushPin } from "../lib/physics";

const TARGET = "SS--:SS--:-S--:SS--:-S--:cS--:SS--:-S--:SS--:-S--:cS--";
const CAP = 11;

function columns(code: string): string[] {
  const rows = parseCode(code, CAP);
  const result = ["", "", "", ""];
  for (let q = 0; q < 4; q += 1) {
    let text = "";
    for (let l = 0; l < CAP; l += 1) text += rows[l]?.[q] ?? "-";
    result[q] = text.replace(/-+$/g, "");
  }
  return result;
}

const started = performance.now();
const result = solveAnyPinPush(parseCode(TARGET, CAP), CAP, {
  transitionLimit: 100_000_000,
});
const elapsedMs = performance.now() - started;
let replay: string | null = null;
let replayOk = false;
let predecessorColumns: string[] | null = null;
let predecessorRank0: boolean | null = null;
if (result.ok && result.predecessor !== undefined) {
  replay = rowsToCode(pushPin(parseCode(result.predecessor, CAP), CAP));
  replayOk = replay === TARGET;
  predecessorColumns = columns(result.predecessor);
  predecessorRank0 = isRank0Code(result.predecessor, CAP);
}
console.log(JSON.stringify({
  target: TARGET,
  cap: CAP,
  elapsedMs,
  result,
  predecessorColumns,
  predecessorRank0,
  replay,
  replayOk,
}, null, 2));
