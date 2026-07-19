# Windows launcher fix 1.1.1

원인:

1. `scripts/serve-static.mjs`가 `new URL(...).pathname`을 OS 파일 경로로 직접 사용했습니다.
   Windows에서는 `/C:/...`가 되어 정적 루트가 잘못 계산될 수 있습니다.
2. `run.bat`이 로컬 서버의 listen 완료 전에 브라우저를 열었습니다.
3. 기존 launcher는 Node 버전, npm 누락, 포트 충돌을 충분히 설명하지 않았습니다.

수정:

- `fileURLToPath()`로 Windows/POSIX 경로를 변환합니다.
- 요청 경로의 선행 `/`와 `\\`를 제거하고 정적 루트 탈출을 차단합니다.
- 서버 listen 이후 브라우저를 엽니다.
- `run.bat`은 Node 20 이상, 사전 빌드 및 서버 파일을 검사합니다.
- `build.bat`은 `npm ci`와 전체 검증 후 앱을 실행합니다.
- `npm start`와 `npm run preview`도 사전 빌드 정적 서버를 실행합니다.

검증:

- Vitest: 6 files / 23 tests PASS
- TypeScript: PASS
- Next.js production static export: PASS
- Worker smoke: PASS
- Static smoke: PASS
- Real HTTP server: `/` and `/solver.worker.js` returned HTTP 200
