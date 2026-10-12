Optional extra CA certificates for networks that intercept TLS (some build sandboxes and corporate proxies).
Put `*.crt` files here and the Docker builds trust them for pip, npm, apt and provider calls.
On a normal laptop this folder stays empty. `*.crt` files are git-ignored.
