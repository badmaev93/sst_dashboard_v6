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

### Applied Usability Implementations in GFS Dashboard v6:

- **Local-First Sync (`localStorage`):** We integrated automatic persistence of active GFS forecast parameters, toggle states (blur, smooth, contours, wind, stations), map scale, and current period indices. Settings persist immediately upon change and restore automatically upon reload, guaranteeing a cohesive and fast starting state.
- **High-Throughput Keyboard Control Panel:** We mapped global keyboard listeners so users can cycle forecast periods with `ArrowLeft`/`ArrowRight`, toggle map overlays instantly (`w` for wind, `s` for stations, `c` for coastline), and cycle GFS visualization parameters using `p`.
- **Keyboard Context Safety:** Shortcuts are ignored when input tags, textareas, dropdowns, or contenteditable areas are active, preventing accidental triggers while maintaining a high-speed mouse-free workflow.

## 2026-07-28 - Elevating Shortcut Discovery for High-Throughput Web GIS Maps
**Learning:** For application dashboards with rich keyboard-first layout control, hidden hotkeys remain completely unused unless discoverability is designed natively into the viewport. Placing a subtle hotkey legend at the footer of the initial multi-grid screen and providing a dedicated collapsible "Hotkeys" panel within the primary sidebar drastically accelerates layout onboarding and improves feature adoption without cluttering the visual interface.
**Action:** When mapping global keyboard shortcuts in complex mapping/data interfaces, always accompany them with a subtle footer hint on comparison screens and a collapsible hotkey guide in the main sidebar.

## 2026-08-01 - Hierarchical Keyboard Dismissal Pattern for Multi-Module GIS Dashboards
**Learning:** In complex GIS applications with multiple active overlay modules (such as Calendar, Requests, and Agent Monitoring), a generic global Escape key listener can easily disrupt user state transitions if it aggressively closes parent panels. Implementing a hierarchical dismissal strategy—which systematically checks and triggers the click actions of innermost close buttons (details, forms, and alert popups) first before dismissing full-screen viewports—preserves modular cleanups, guarantees predictable navigation, and minimizes cognitive load.
**Action:** Always implement global Escape handlers to search for active nested modals or sub-elements sequentially before bubble-up actions dismiss parent overlays or control panels.
