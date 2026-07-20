# Palette's UX/A11y Journal

This journal contains critical learnings on UX and accessibility enhancements for the SST Dashboard application.

## 2026-07-18 - Synchronizing Accessible States for Off-Canvas Menus
**Learning:** Icon-only slide-out panel toggle buttons must communicate both their purpose (using descriptive `aria-label` text) and their open/closed states (`aria-expanded`) to assistive technologies. Simply toggling a CSS class on the panel container is insufficient for screen readers; the interactive trigger button itself must statefully reflect the menu's visibility dynamically via JavaScript.
**Action:** Always ensure off-canvas toggle triggers have static `aria-label` labels and that their `aria-expanded` attributes are programmatically updated inside the corresponding toggle and close JavaScript handler functions.
