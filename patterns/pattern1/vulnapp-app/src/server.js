import http from "node:http";

export function createServer() {
  return http.createServer((req, res) => {
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.setHeader("Cache-Control", "no-store");
    if (req.method === "GET" && req.url === "/health") {
      res.writeHead(200);
      res.end(JSON.stringify({ status: "ok" }));
      return;
    }
    if (req.method === "GET" && req.url === "/api/items") {
      // Non-sensitive fixture data. Authentication and real business logic are out of scope.
      res.writeHead(200);
      res.end(JSON.stringify({ items: ["example"] }));
      return;
    }
    res.writeHead(404);
    res.end(JSON.stringify({ error: "not_found" }));
  });
}

if (process.argv[1] && import.meta.url === new URL('file://' + process.argv[1]).href) {
  const port = Number(process.env.PORT || 3000);
  createServer().listen(port, "0.0.0.0", () => console.log("pattern1 app listening"));
}
