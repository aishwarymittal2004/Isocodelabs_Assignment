<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## Project rules
- All prototype data lives in src/lib/mock-data.ts; screens read from it so swapping to a real backend later touches one module.
- Buyer screens use src/components/site.tsx; sales workspace screens (under /sales) use src/components/ops.tsx for a denser, data-first look.
