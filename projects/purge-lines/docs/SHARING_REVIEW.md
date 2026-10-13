# Shareability review

Source: [IDcrazy123/All-Config-Voron prime-lines.cfg](https://github.com/IDcrazy123/All-Config-Voron/blob/7ef1a9fd7338a6275690290820f5aa01249d65e3/config/Printer-Setup/prime-lines.cfg), reviewed 2026-10-13. Upstream repository has no repository-wide license declaration in its API metadata. The owner requested this derivative and publication; new purge implementation is supplied under the included MIT license. Do not assume unrelated files in that repository share this license.

The original macro is useful on its existing configured machine. Direct reuse requires the same tool registry, heater routing, tool macros, slicer recovery ownership and bed geometry. Travel limits are not a usable-bed rectangle; clamping each pass may collapse multiple strokes near an edge. Unknown tool-temperature parameters can be ignored, and old G-code state restoration around tool switches can reintroduce previous coordinate origins. Retraction and first-layer values are local contracts.

The community builder replaces these implicit assumptions with explicit mappings/limits, preflight rejection, a preview and an exit-state contract. It supports standard Klipper status objects and reviewed selection adapters. Klipper-toolchanger/StealthChanger style Tn macros are a supported integration pattern after review, not an automatic declaration that KTC or every firmware behaves identically.

Two operator-supplied photos show the ORIGINAL macro's purge strokes. They are not a new hardware test of version 1.0.0. This release is experimental, with synthetic regression and template checks; installation and physical trials are separate authorized actions.
