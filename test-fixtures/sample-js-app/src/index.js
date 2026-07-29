"use strict";

/**
 * Minimal Express-style entrypoint for CODESTRATA JavaScript detection demos.
 * This is intentionally small and does not require `npm install` to assess.
 */

const http = require("http");

function createApp() {
  return {
    listen(port, callback) {
      const server = http.createServer((_request, response) => {
        response.writeHead(200, { "Content-Type": "application/json" });
        response.end(JSON.stringify({ ok: true, service: "sample-js-app" }));
      });
      return server.listen(port, callback);
    },
  };
}

if (require.main === module) {
  const port = Number(process.env.PORT || 3000);
  createApp().listen(port, () => {
    // eslint-disable-next-line no-console
    console.log(`sample-js-app listening on ${port}`);
  });
}

module.exports = { createApp };
