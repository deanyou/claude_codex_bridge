# Tailscale Tailnet Stable Route

Date: 2026-06-23
Status: Source-side `cc-bridge update mobile` onboarding landed in reviewed
worktree; live physical-device smoke pending

## Purpose

Define the stable Tailscale route for using CC_BRIDGE Mobile from a phone or iPad to
control a user's computer without public DNS, router port forwarding,
Cloudflare credentials, or a public CC_BRIDGE relay.

This route is for private-network users and developer dogfood. It does not
replace [Decision 011](../decisions/011-relay-default-remote-route.md): CC_BRIDGE
Relay remains the default not-on-LAN route for ordinary users. Tailnet remains
a route provider below `GatewayTransport`.

## Official References

- Tailscale Serve shares a local service securely inside a tailnet and can
  reverse proxy to a local HTTP service:
  <https://tailscale.com/docs/reference/tailscale-cli/serve>.
- MagicDNS gives tailnet devices full names such as
  `<machine>.<tailnet>.ts.net`:
  <https://tailscale.com/docs/features/magicdns>.
- Tailnet HTTPS certificates are administered through Tailscale HTTPS support:
  <https://tailscale.com/docs/how-to/set-up-https-certificates>.
- Direct connections are preferred for latency/throughput; DERP relay is a
  fallback and can be slower:
  <https://tailscale.com/docs/reference/connection-types>.
- Grants are the preferred modern tailnet access-control syntax:
  <https://tailscale.com/docs/reference/examples/grants>.

## Stable Shape

Keep the CC_BRIDGE gateway loopback-only and let Tailscale Serve publish it inside
the tailnet:

```text
phone/iPad Tailscale app
  -> tailnet HTTPS origin
  -> tailscale serve reverse proxy on the computer
  -> 127.0.0.1:8787 cc-bridge mobile gateway
  -> cc-bridge-daemon + CC_BRIDGE project tmux socket
```

Use the Tailscale App Store stable client for phones and iPads by default.
Tailscale TestFlight/unstable builds are only for troubleshooting a
Tailscale-client issue or validating a new Tailscale feature.

Do not use Tailscale Funnel for this route. Funnel exposes a service to the
public internet; CC_BRIDGE Mobile's tailnet route should stay available only to
authorized tailnet identities. Do not bind `cc-bridge mobile serve` to
`0.0.0.0` or to the tailnet interface.

## Prerequisites

- The computer and phone/iPad are logged in to the same tailnet.
- MagicDNS is enabled, and the computer has a stable machine name such as
  `cc-bridge-host`.
- Tailnet HTTPS is enabled for the computer's MagicDNS name.
- The computer can run a CC_BRIDGE build that supports the optional mobile bundle:
  `cc-bridge update mobile` and `cc-bridge mobile serve --route-provider tailnet`.
- The computer can stay awake while CC_BRIDGE Mobile is connected.
- The phone/iPad has Tailscale VPN connected before pairing or reconnecting.

## Computer Setup

Preferred user-facing setup should be:

```bash
cc-bridge update mobile
```

That command should install/repair the optional CC_BRIDGE Mobile host bundle, detect
or install Tailscale with explicit confirmation, open the Tailscale login flow
when needed, then proceed to the gateway and QR steps. The lower-level command
shape remains documented here so the route can be debugged and tested.

Install and authenticate Tailscale, then give the host a stable name:

```bash
sudo tailscale up --hostname=cc-bridge-host
tailscale status
```

For a stricter access model, first add the `tagOwners` policy shown below,
then authenticate the host with a service tag and target the tag in grants:

```bash
sudo tailscale up --hostname=cc-bridge-host --advertise-tags=tag:cc-bridge-mobile
```

Enable MagicDNS and HTTPS in the Tailscale admin console. The stable public
route metadata should use the origin-only tailnet HTTPS URL:

```text
https://cc-bridge-host.<tailnet>.ts.net:8787
```

Start the CC_BRIDGE Mobile gateway in the CC_BRIDGE project directory:

```bash
cc-bridge mobile serve \
  --listen 127.0.0.1:8787 \
  --public-url https://cc-bridge-host.<tailnet>.ts.net:8787 \
  --route-provider tailnet
```

In a second terminal, publish the loopback gateway inside the tailnet:

```bash
tailscale serve --bg --https=8787 http://127.0.0.1:8787
tailscale serve status
```

The fixed `127.0.0.1:8787` listen port is intentional. It keeps the Tailscale
Serve target stable and keeps the public Tailnet HTTPS port aligned with the
gateway listen port.

## Phone Or iPad Setup

1. Install Tailscale stable from the App Store and log in to the same tailnet.
2. Turn on the Tailscale VPN connection.
3. In CC_BRIDGE Mobile, use the gateway pairing flow:

```text
Route: Tailnet
Gateway URL: https://cc-bridge-host.<tailnet>.ts.net:8787
Pairing code: value printed by cc-bridge mobile serve
```

After pairing, CC_BRIDGE's device token, scopes, terminal tokens, revocation, project
identity, namespace epoch, and terminal target validation remain owned by the
user's CC_BRIDGE host. Tailscale identity is an outer network-access boundary, not a
replacement for CC_BRIDGE pairing.

## Tailnet Policy Shape

Prefer grants that allow only the phone/iPad identity to reach the CC_BRIDGE Mobile
host on TCP 8787. Example shape:

```json
{
  "groups": {
    "group:cc-bridge-mobile-users": ["user@example.com"]
  },
  "tagOwners": {
    "tag:cc-bridge-mobile": ["autogroup:admin"]
  },
  "grants": [
    {
      "src": ["group:cc-bridge-mobile-users"],
      "dst": ["tag:cc-bridge-mobile"],
      "ip": ["tcp:8787"]
    }
  ]
}
```

Use the Tailscale admin console preview/tests before applying policy changes.
If the host is not tagged, target the concrete host or owner identity instead,
but keep the destination limited to TCP 8787 for this route.

## Source Implementation Evidence

Lead accepted the source-side onboarding package on 2026-06-23:

- Worktree: `/home/bfly/yunwei/cc-bridge_source_mobile_update_tailnet`
- Branch: `worker1/mobile-update-tailnet`
- Commits:
  - `b6e148f2 feat: add mobile tailnet update onboarding`
  - `d73ae650 fix: align mobile tailnet serve port`
- Changed source files:
  - `lib/cli/services/mobile_update.py`
  - `lib/cli/management_runtime/commands_runtime/update.py`
  - `lib/cli/router.py`
  - `test/test_cli_services_mobile_update.py`
  - `test/test_cli_management_update.py`
  - `test/test_v2_cli_parser.py`
  - `test/test_v2_cli_router.py`

Verification reported by lead:

- focused/relevant tests after follow-up: 147 passed;
- worker full pytest before follow-up: 2993 passed, 2 skipped;
- `python -m py_compile ...`: passed;
- `git diff --check`: passed;
- reviewer1 accepted the final stack.

Security and UX boundaries confirmed by review: no Funnel, no token/password
storage, no ACL/grant edits, loopback-only gateway, non-loopback listen
rejection preserved, and Tailnet route remains command metadata only. The
follow-up fixed the generated route to keep
`--public-url https://<host>:8787` aligned with
`tailscale serve --bg --https=8787 http://127.0.0.1:8787`.

## Diagnostics And Smoke

Before pairing:

```bash
tailscale status
tailscale ping <phone-or-ipad-name>
tailscale netcheck
curl -fsS https://cc-bridge-host.<tailnet>.ts.net:8787/v1/health
```

The mobile repo also provides a read-only preflight that packages the required
host/device checks into one JSON result:

```bash
PATH="/home/bfly/.local/share/android-sdk/platform-tools:$PATH" \
  tools/mobile_physical_tailnet_preflight.py \
  --gateway-url https://cc-bridge-host.<tailnet>.ts.net:8787
```

This preflight must return `status: ok` before claiming a physical
phone/iPad Tailnet smoke. It only checks readiness: attached physical Android
device, Android boot completion, host `tailscale status --json`, Tailscale
Serve public HTTPS port plus loopback origin, and gateway `/v1/health`. It
does not install Tailscale, save tokens, modify ACL/grants, start Funnel, or
change gateway state.

During smoke, validate the full gateway path, not only `/v1/health`:

- pairing claim succeeds with `route_provider: tailnet`;
- `GatewayRouteDiagnostics` is ready;
- `/v1/devices/me` reports the same route provider and gateway origin as the
  stored profile;
- ProjectView and focus calls work;
- terminal-open returns a
  `wss://cc-bridge-host.<tailnet>.ts.net:8787/v1/terminals/...` WebSocket URL;
- terminal output/input/paste/resize/close and reconnect pass;
- `cc-bridge mobile revoke <device_id>` blocks later project list and terminal-open.

If performance is poor, first inspect whether the connection is direct or
relayed:

```bash
tailscale status
tailscale ping <phone-or-ipad-name>
```

`direct` is preferred. `relay` or `DERP` is acceptable for low-volume CC_BRIDGE
Mobile control but can add latency; it should be called out in smoke evidence
when observed.

## Failure Modes

- Phone not logged in or VPN off: tailnet URL is unreachable.
- MagicDNS disabled or wrong host name: `cc-bridge-host.<tailnet>.ts.net` does not
  resolve.
- Tailnet HTTPS disabled: `tailscale serve --https=8787` cannot provide the
  stable HTTPS origin.
- `tailscale serve` points at the wrong local port: `/v1/health` or pairing
  fails even though Tailscale connectivity works.
- CC_BRIDGE gateway started without `--public-url`: pairing may store a loopback URL
  that the phone cannot reach.
- CC_BRIDGE gateway started with the wrong route provider: diagnostics fail
  `route_provider_scope`.
- Tailscale access policy is too broad: more tailnet devices than intended can
  reach the CC_BRIDGE gateway origin.
- DERP-only path: CC_BRIDGE Mobile may work, but latency can be higher than direct
  P2P.

## Acceptance Gate

Tailnet route is stable enough to document for private users when one physical
phone or iPad on non-LAN networking can:

- reach `https://cc-bridge-host.<tailnet>.ts.net:8787/v1/health`;
- pair through the CC_BRIDGE Mobile gateway using `route_provider: tailnet`;
- load projects and ProjectView through the same app screens used for LAN,
  relay, and Cloudflare;
- send to one selected agent through pane-backed chat and observe output in
  the timeline;
- open explicit raw terminal, send input, paste, resize, close, and reconnect;
- revoke the paired device locally and prove the old device token no longer
  controls project list or terminal-open;
- record whether the Tailscale path was direct, peer-relay, or DERP relay.

## Deferrals

- Do not make Tailnet the ordinary-user default route.
- Do not require all users to join the maintainer's tailnet.
- Do not expose CC_BRIDGE Mobile through Tailscale Funnel for normal operation.
- Do not add tailnet-specific fields to ProjectView, project ids, terminal ids,
  terminal frame schemas, or content ids.
