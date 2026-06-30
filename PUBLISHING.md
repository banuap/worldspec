# Publishing the WorldSpec specification

This repo is scaffolded to publish WorldSpec "like a real standard": a hosted,
versioned spec with a stable namespace, a permissive license, a machine-readable
schema, a conformance suite, and a citable DOI. Most of that is already in the
repo (`docs/`, `conformance/`, `LICENSE-spec`, `CITATION.cff`, `GOVERNANCE.md`).
The steps below are the **manual actions** that must be done outside the code.

## 1. Turn on GitHub Pages (publishes the spec site)

1. Push to `main` (already done for the scaffold).
2. GitHub → repo **Settings → Pages**.
3. **Source:** *Deploy from a branch*. **Branch:** `main`, **Folder:** `/docs`.
4. Save. After the build, the site is live at:
   - Home: `https://banuap.github.io/worldspec/`
   - Spec (this version): `https://banuap.github.io/worldspec/spec/0.1/`
   - Latest: `https://banuap.github.io/worldspec/spec/`
   - Namespace: `https://banuap.github.io/worldspec/ns/0.1/`
   - Schema: `https://banuap.github.io/worldspec/schemas/worldspec-model-0.1.schema.json`

> The site uses Jekyll (`docs/_config.yml`, theme `jekyll-theme-cayman`). If a
> page ever fails to build because a code sample contains `{{` or `{%`, wrap
> that snippet in `{% raw %}…{% endraw %}`.

## 2. (Recommended) A permanent, vendor-neutral namespace via w3id.org

`banuap.github.io` is fine to start, but a project that outlives one GitHub
account should own its identifiers. [w3id.org](https://w3id.org) provides
permanent, redirecting URLs used by many specifications, free:

1. Fork `https://github.com/perma-id/w3id.org`.
2. Add a folder `worldspec/` with a `.htaccess` that 302-redirects to the
   current Pages site (and can be repointed later without breaking links), e.g.:
   ```apache
   # worldspec/.htaccess
   RewriteEngine on
   RewriteRule ^spec/(.*)$ https://banuap.github.io/worldspec/spec/$1 [R=302,L]
   RewriteRule ^ns/(.*)$   https://banuap.github.io/worldspec/ns/$1   [R=302,L]
   ```
3. Open a PR. Once merged, your stable IDs become `https://w3id.org/worldspec/…`.
4. Update the namespace/`$id` URLs in `docs/` and the schema to the w3id form.

A custom domain (e.g. `worldspec.org`) is an alternative — set it in
**Settings → Pages → Custom domain** and update the URLs.

## 3. Mint a DOI (makes the spec citable like a paper)

1. Sign in at [zenodo.org](https://zenodo.org) with GitHub.
2. Enable the repository under **Zenodo → GitHub**.
3. In GitHub, create a **release** (e.g. `v0.1.0`). Zenodo archives it and
   mints a DOI automatically.
4. Add the DOI badge to `README.md` and the `doi:` field to `CITATION.cff`.

`CITATION.cff` already renders a "Cite this repository" button on GitHub.

## 4. Register the media types (provisional)

The spec declares `application/worldspec+yaml` (source) and
`application/worldspec-ir+json` (canonical IR). To register them provisionally
with IANA, email `media-types@iana.org` using the template in
[RFC 6838 §5.7](https://www.rfc-editor.org/rfc/rfc6838#section-5.7). Minimum
fields: type/subtype, required/optional parameters, encoding considerations,
security considerations, and a change controller. Until registered, the `+yaml`
/ `+json` structured-suffix forms are still usable.

## 5. Path to a formal standards venue (optional, later)

The realistic analog to "how OWL is published" without W3C membership is a
**W3C Community Group**: anyone can propose one, it has no fee, and it can
publish *Community Group Reports* and a *Final Specification* under the W3C
Community Final Specification Agreement (which includes patent commitments).
Alternatives: OASIS, ECMA, or an IETF Independent-Submission RFC. Defer this
until there is real external implementation interest; the Tier-1/Tier-2
artifacts here are exactly what such a group would start from.

## Checklist

- [ ] Pages enabled (Settings → Pages → /docs)
- [ ] Site resolves at the URLs in §1
- [ ] (Optional) w3id.org redirect merged; URLs updated
- [ ] Zenodo enabled; `v0.1.0` release cut; DOI added to README + CITATION.cff
- [ ] Media types submitted to IANA (provisional)
- [ ] Spec license (CC BY 4.0) + implementation grant reviewed (`LICENSE-spec`, spec §Status)
