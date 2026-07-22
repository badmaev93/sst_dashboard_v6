# Palette's UX/A11y Journal

This journal contains critical learnings on UX and accessibility enhancements for the SST Dashboard application.

## 2026-07-18 - Synchronizing Accessible States for Off-Canvas Menus
**Learning:** Icon-only slide-out panel toggle buttons must communicate both their purpose (using descriptive `aria-label` text) and their open/closed states (`aria-expanded`) to assistive technologies. Simply toggling a CSS class on the panel container is insufficient for screen readers; the interactive trigger button itself must statefully reflect the menu's visibility dynamically via JavaScript.
**Action:** Always ensure off-canvas toggle triggers have static `aria-label` labels and that their `aria-expanded` attributes are programmatically updated inside the corresponding toggle and close JavaScript handler functions.

## 2026-07-22 - Keyboard Escape Handling and ARIA Semantics for Complex Navigation Tabs and Modals
**Learning:** High-impact accessibility in custom vanilla JS applications requires providing explicit keyboard escape hatches (such as listening for 'Escape' keypresses) to dismiss modal/popover states and custom dialogs. Concurrently, custom tab controls must use explicit tab-role boundaries (`role="tablist"`/`role="tab"`) and dynamic state attributes (`aria-selected`) to represent visual states accurately to screen readers.
**Action:** When creating custom vanilla JS UI dialogs or navigation tabs, always map the visual state transitions directly to standard ARIA attributes in real-time, and register explicit Escape-key keydown handlers to dismiss transient overlay elements seamlessly.
