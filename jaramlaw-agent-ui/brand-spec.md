# JaramLaw UI Brand Specification

## Product Character

JaramLaw is a calm, evidence-led family legal and policy service. Parent screens prioritize immediate tasks, deadlines, and source confidence. Operator tools remain visibly separate.

## Visual System

- Primary ink: `#18342c`; action green: `#17624c`; link blue: `#245f8a`; attention amber: `#a65d18`.
- Canvas and panels use neutral white and gray surfaces; color identifies meaning rather than decoration.
- Panels use at most `8px` corner radii. Status chips may use pill geometry.
- Typography uses the system Korean sans-serif stack in `src/index.css`; letter spacing stays at `0`.
- Icons come from `lucide-react` and supplement, never replace, accessible labels.

## Interaction Rules

- Parent navigation: Today, Consultation, Documents, Laws. Mobile uses a fixed bottom tab bar.
- Operator routes live under `#admin/*` and require the operator API boundary.
- Every generated result states whether it came from the Python workflow or bundled seed data.
- Risk is qualitative triage, never a statistical probability.
- Uploaded files are plain-text `.txt` or `.md`, 1MB maximum, with PII removal guidance.

## Source Assets

- Product mark: Lucide `Scale` icon rendered by `src/App.tsx`.
- Hero photography: `/public/assets/jaramlaw-parent-guidance-hero.png` with a solid readability overlay defined in `src/index.css`.
- No gradients, decorative blobs, stock illustrations, or unverified real-time claims.
