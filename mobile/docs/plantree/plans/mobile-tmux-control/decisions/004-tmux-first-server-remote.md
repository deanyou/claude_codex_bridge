# Decision 004: Tmux-First Server Remote

Date: 2026-06-18
Status: Proposed

## Decision

Make the phone/iPad product a tmux-first remote client for server-side CC_BRIDGE
sessions. The main task is to control CC_BRIDGE tmux panes running on the server, not
to create an independent mobile agent application.

Use a native Flutter app as the preferred client surface. Keep tmux-mobile as a
server-side terminal/gateway reference, not the primary mobile client base.

## Rationale

CC_BRIDGE's everyday working surface is already tmux. A mobile/iPad client is most
valuable when it lets the user connect to the same server-side workspace and
operate existing CC_BRIDGE panes remotely.

The user wants a native Android and iOS/iPadOS client. A web terminal alone
does not provide the desired QR pairing, native reconnect, notification, and
phone/iPad interaction polish. ServerBox and MuxPod show that a Flutter native
tmux/SSH client can provide a better base while still connecting to server-side
CC_BRIDGE tmux sessions.

## Consequences

- Interactive terminal control is a primary workflow, not a deferred add-on.
- CC_BRIDGE ask/composer, Comms, and Markdown are enhancement layers around the tmux
  remote.
- The mobile client should stay thin; CC_BRIDGE and providers continue running on the
  server.
- Generic tmux operations must be filtered or wrapped so CC_BRIDGE-managed sessions
  remain consistent.
- The first implementation should adapt a native Flutter terminal/tmux client
  to CC_BRIDGE project sockets and `cc-bridge-daemon` metadata.
- tmux-mobile remains valuable for socket-aware terminal WebSocket and gateway
  tests, especially if a CC_BRIDGE gateway transport is used.

## Validation Path

The decision is validated if a prototype can:

1. connect a phone/iPad to an active server-side CC_BRIDGE tmux session;
2. switch CC_BRIDGE projects without exposing unrelated tmux sessions;
3. switch/focus CC_BRIDGE agents and windows through CC_BRIDGE authority;
4. type, paste, resize, and reconnect without stopping server-side CC_BRIDGE;
5. keep Comms/Markdown/status visible as secondary context;
6. prevent stale or destructive tmux actions by default.
