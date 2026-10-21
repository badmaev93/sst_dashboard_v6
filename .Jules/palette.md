# Palette's UX/A11y Journal

This journal contains critical learnings on UX and accessibility enhancements for the SST Dashboard application.

## 2026-07-18 - Synchronizing Accessible States for Off-Canvas Menus
**Learning:** Icon-only slide-out panel toggle buttons must communicate both their purpose (using descriptive `aria-label` text) and their open/closed states (`aria-expanded`) to assistive technologies. Simply toggling a CSS class on the panel container is insufficient for screen readers; the interactive trigger button itself must statefully reflect the menu's visibility dynamically via JavaScript.
**Action:** Always ensure off-canvas toggle triggers have static `aria-label` labels and that their `aria-expanded` attributes are programmatically updated inside the corresponding toggle and close JavaScript handler functions.

## 2026-07-22 - Keyboard Escape Handling and ARIA Semantics for Complex Navigation Tabs and Modals
**Learning:** High-impact accessibility in custom vanilla JS applications requires providing explicit keyboard escape hatches (such as listening for 'Escape' keypresses) to dismiss modal/popover states and custom dialogs. Concurrently, custom tab controls must use explicit tab-role boundaries (`role="tablist"`/`role="tab"`) and dynamic state attributes (`aria-selected`) to represent visual states accurately to screen readers.
**Action:** When creating custom vanilla JS UI dialogs or navigation tabs, always map the visual state transitions directly to standard ARIA attributes in real-time, and register explicit Escape-key keydown handlers to dismiss transient overlay elements seamlessly.

## 2026-07-25 - Frictionless Local-First Persistence and Keyboard-First Map Controls
**Learning:** Drawing inspiration from Super Productivity, powerful developer-oriented web applications benefit immensely from a "local-first" philosophy where configurations, layout toggles, and state are persisted instantly via localStorage, eliminating layout shifts and network round-trips. Furthermore, full keyboard navigability (such as using keybindings to switch parameters or toggle map animations) turns a point-and-click dashboard into a high-throughput power tool.
**Action:** Always design dashboard interfaces to remember UI settings locally without forcing user log-ins, and implement solid global keyboard shortcut listeners to accelerate navigation.

## Best Usability Practices and Paradigm Analysis: Super Productivity

Super Productivity (https://github.com/super-productivity/super-productivity) is an open-source, local-first personal organizer designed for power users and developers. Analyzing its interface and workflow paradigms reveals several cornerstone usability best practices:

1. **Frictionless Quick Capture & Inline Short Syntax:**
   - *Quick Task/Request Capture:* Users can capture tasks in seconds from any view using global hotkeys (e.g., `Shift+A`), avoiding multi-step form dialogs.
   - *Short Syntax Input Parsing:* Inline commands (like `#tag`, `+project`, `1h30m`, `@assignee`) allow users to set attributes while typing without leaving the keyboard.

2. **The "Local-First" Paradigm (Sub-Millisecond Speed & Zero Downtime):**
   - No mandatory cloud sync or registration barriers.
   - All state, active filters, user options, and workspace preferences are persisted instantly in local storage (`localStorage` / `IndexedDB`).
   - Optional End-to-End Encrypted sync (SuperSync / WebDAV / Dropbox / Git) gives users total data ownership.

3. **Keyboard-Centric Ergonomics & Shortcut Discovery:**
   - Every primary action is mapped to global keyboard shortcuts.
   - High discoverability via hotkey legends and dedicated shortcut panels ensures users transition smoothly from mouse navigation to power-user keyboard speed.
   - Safety checks prevent hotkey collisions when typing inside text inputs, contenteditables, or dropdowns.

4. **Bi-Directional Input & Layout Resilience:**
   - Systems accommodate international keyboard layouts and characters (e.g., mapping Latin keys to Cyrillic equivalents like `W -> Ц`, `S -> Ы`, `C -> С`, `P -> З`), ensuring keybindings work regardless of the user's active keyboard layout.

5. **Contextual Side-Notes & Deep-Link Attachments:**
   - Tasks and items allow attaching contextual information directly (e.g., Markdown notes, URLs, commands, telemetry logs).
   - Keeps secondary information accessible in collapsible side panels without cluttering the primary list or map view.

6. **Focus & Health-Aware Workflow Controls (Timeboxing & Break Reminders):**
   - Pomodoro/Flowtime timer integration, break reminders, and anti-procrastination prompts encourage sustained focus while preventing burnout during intense operational monitoring sessions.

7. **Structured Daily/Shift Work Reviews & Hand-offs:**
   - Features dedicated end-of-day or shift summary workflows to review completed tasks, track time spent, log anomalies, and prepare hand-off reports for team members or incoming duty shifts.

### Applied Usability Implementations & Ideas for SST Dashboard v6:

- **Local-First Sync (`localStorage`):** Automatic persistence of active GFS forecast parameters, view modes, map scale, contour/smooth toggles, and station overlay preferences. Restores automatically on reload.
- **Global Command Palette (Omni-Bar / Quick Jump):** `Ctrl+K` / `Cmd+K` command overlay allowing hydro-meteorologists to instantly jump to specific stations (e.g., `/st Magadan`), trigger forecast calculations, or file urgent equipment maintenance requests from anywhere in the app.
- **High-Throughput Keyboard Control Panel:** Global keyboard shortcuts to cycle forecast periods (`ArrowLeft`/`ArrowRight`), toggle map overlays (`w` for wind, `s` for stations, `c` for coastline), and cycle parameters (`p`), complete with Cyrillic layout resilience (`Ц`, `Ы`, `С`).
- **Viewport Shortcut Discoverability:** A subtle footer hotkey legend on comparison screens and a collapsible hotkey guide in the main sidebar.
- **Contextual Side Notes for Duty Requests & Tasks:** Support for inline attachments and context notes on station monitoring tasks and maintenance requests.
- **Focus Blocks & Timeboxing:** Dedicated focus time slots in the calendar module to support undisturbed forecast modeling and telemetry analysis during operational shifts.
- **Shift Review Workflow:** End-of-shift daily review summaries in the duty schedule module to review station status logs, active warnings, and hand off active requests to incoming duty officers.

## 2026-07-28 - Elevating Shortcut Discovery for High-Throughput Web GIS Maps
**Learning:** For application dashboards with rich keyboard-first layout control, hidden hotkeys remain completely unused unless discoverability is designed natively into the viewport. Placing a subtle hotkey legend at the footer of the initial multi-grid screen and providing a dedicated collapsible "Hotkeys" panel within the primary sidebar drastically accelerates layout onboarding and improves feature adoption without cluttering the visual interface.
**Action:** When mapping global keyboard shortcuts in complex mapping/data interfaces, always accompany them with a subtle footer hint on comparison screens and a collapsible hotkey guide in the main sidebar.

## 2026-07-29 - Hierarchical Escape Dismissal for Dynamic Multi-Module Overlays
**Learning:** In highly interactive custom single-page applications (SPAs) with overlapping modal dialogs, dynamic forms, and multiple full-screen overlay views, standard keyboard navigation can break if 'Escape' handling is scattered or nonexistent. By implementing a centralized, hierarchical 'keydown' listener, we can programmatically query and click the active context's close buttons (e.g., forms before overlays, and popups before main modules). This preserves module-level state transition cleanups, prevents double-handlers, and guarantees smooth, intuitive keyboard access.
**Action:** Always design a centralized dynamic hierarchical dispatcher for keyboard Escape interactions in rich modular SPA frontends to ensure context-aware modal cleanup and standard-compliant web accessibility.

## 2026-07-30 - Dialog Accessibility and Seamless Cross-Module View State Synchronization
**Learning:** In modular vanilla JS single-page applications, dynamically rendered side drawers (such as station detail panels) require explicit dialog semantics (`role="dialog"`, `aria-label`, `tabindex="-1"`) and programmatic focus placement upon creation to ensure screen readers and keyboard users immediately receive dialog context. Furthermore, direct cross-module navigation actions (like jumping to an AI forecast from a station popup) must invoke the top-level tab navigation handler (`showDetailTab`) rather than localized view toggles to keep SPA top navigation tab styles and `aria-selected` attributes strictly synchronized.
**Action:** Always set standard dialog ARIA attributes and focus when opening dynamic overlay drawers, and ensure cross-module triggers delegate to the central navigation coordinator to synchronize accessibility state.
