# Meme-ology design system

The repository follows the design system in the workspace-level [DESIGN.md](../DESIGN.md). It is a warm editorial field guide for meme context and source-aware discovery.

Design read: internet-culture reference for curious readers and developers, contemporary culture magazine with reference-library precision, **ENERGY 3 / RHYTHM 3 / MOTION 1**.

Use the paper palette (`#F5F2E9`, `#191919`, `#595650`, `#B83222`), Fraunces or Georgia for editorial titles, Public Sans or a system sans-serif for interface text, and JetBrains Mono only for API material. Keep the feature image uncropped, put source and date beneath every entry, label KYM ordering explicitly, and expose stale or unavailable states.

The discover page, `/meme/{id}` detail page, API playground, and source notes must preserve the evidence rules: records come from API responses, popularity claims name their source, and unknown details remain unknown. Responsive layouts must reflow at 767px and below with 44px controls, no horizontal overflow, visible focus, reduced-motion support, and a working paper/charcoal theme toggle.
