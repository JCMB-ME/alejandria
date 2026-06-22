<script lang="ts">
  /**
   * OPDS landing page — shows the OPDS URL and client setup instructions.
   */
</script>

<svelte:head>
  <title>OPDS — Alejandría</title>
</svelte:head>

<div class="p-6 md:p-8 max-w-2xl mx-auto">
  <h1 class="font-serif text-2xl md:text-3xl mb-4">OPDS Catalog</h1>
  <p class="text-[var(--text-muted)] mb-6">
    OPDS (Open Publication Distribution System) lets external reader apps browse and download from your library.
  </p>

  <section class="card p-5 mb-6">
    <h2 class="text-lg font-semibold mb-3">Catalog URL</h2>
    <code class="block p-3 rounded text-sm font-mono break-all" style="background: var(--bg);">
      {window?.location.origin || ''}/opds
    </code>
    <p class="text-sm text-[var(--text-muted)] mt-2">
      Use this URL in your OPDS-compatible reader app.
    </p>
  </section>

  <section class="card p-5 mb-6">
    <h2 class="text-lg font-semibold mb-3">Compatible apps</h2>
    <ul class="space-y-2 text-sm">
      <li><strong>KOReader</strong> (e-ink devices) — Add OPDS catalog in settings</li>
      <li><strong>Calibre Companion</strong> (iOS/Android) — Add new connection</li>
      <li><strong>Moon+ Reader</strong> (Android) — Network → OPDS</li>
      <li><strong>Marvin</strong> (iOS) — Sources → OPDS</li>
      <li><strong>Cantook</strong> (iOS) — Add library</li>
      <li><strong>KyBook 3</strong> (iOS) — OPDS catalog</li>
    </ul>
  </section>

  <section class="card p-5">
    <h2 class="text-lg font-semibold mb-3">Search endpoint</h2>
    <p class="text-sm mb-2 text-[var(--text-muted)]">For apps that support OpenSearch:</p>
    <code class="block p-3 rounded text-sm font-mono" style="background: var(--bg);">
      {window?.location.origin || ''}/opds/search
    </code>
  </section>
</div>
