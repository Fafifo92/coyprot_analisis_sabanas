## 2024-10-25 - Icon-only buttons lack screen reader context
**Learning:** Icon-only buttons (like delete trash cans) missing descriptive labels are completely opaque to screen readers, causing a severe accessibility barrier for visually impaired users. Relying solely on a visual `title` attribute is insufficient for assistive technologies.
**Action:** Always add `aria-label` to buttons containing only icons or SVGs. This small change makes actions explicit and accessible to screen-reader users without affecting visual layout.
