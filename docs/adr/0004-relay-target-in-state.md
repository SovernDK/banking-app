# The hosted callback relay forwards to the target carried in `state`

Enable Banking accepts only https redirect URLs, so the bank returns to a static page on GitHub Pages (`site/callback.html`), which relays the answer to Yiji. At first Yiji ran only on the viewer's machine, so `state` carried the local port and the relay forwarded to `http://127.0.0.1:<port>`. Once Yiji runs on a home server reached over Tailscale (`https://yiji.home.net`), loopback is the wrong machine.

`state` is now `<target>.<nonce>`, where the target is either the local port or Yiji's https origin in base64url, taken from `YIJI_PUBLIC_URL`. The relay accepts only those two shapes, only a bare https origin, and always appends the fixed callback path. We chose this over hard-coding an allowlist of hosts in the page because the site repo is public (it would publish the private hostname) and every new host would need a site redeploy.

The cost is that the relay will forward to any https origin someone puts in a crafted link. What it forwards is a one-time authorisation code. That code is useless without the app's Enable Banking private key, and Yiji rejects any `state` whose nonce it did not issue.
