<script>
  /*
    SelectableTable — sortable, paginated table whose rows filter like a
    DimensionGrid instead of navigating. Self-rendering, so clicks pass the real
    row object and sorting never desyncs selection.

    Writes DimensionGrid fragment shape to $inputs[name]:
      nothing selected -> true ; a row -> ( "COL" in ( 'VALUE' ) )

    Features: reactive header sorting (Evidence-style caret), pagination (rows),
    thin row dividers, optional collapseOnSelect (show only the selected row until
    clicked again), delta formatting.
  */
  import { QueryLoad } from '@evidence-dev/core-components';
  import { getInputContext } from '@evidence-dev/sdk/utils/svelte';
  import { writable } from 'svelte/store';

  export let data;
  export let name;
  export let valueCol;
  export let multiple = false;
  export let columns = undefined;         // [{id,title?,fmt?,align?,downIsGood?}]
  export let initialSort = undefined;     // {col,dir}
  export let rows = 10;                    // rows per page
  export let rowShading = false;
  export let collapseOnSelect = false;    // when a row is selected, show only it

  const inputs = getInputContext();
  const selected = writable([]);

  function toFragment(vals, col) {
    if (!vals || vals.length === 0) return 'true';
    const quoted = vals.map((v) => `'${String(v).replace(/'/g, "''")}'`).join(', ');
    return `( "${col}" in ( ${quoted} ) )`;
  }
  $: $inputs[name] = toFragment($selected, valueCol);

  function toggle(row) {
    const v = row[valueCol];
    selected.update((cur) => {
      const has = cur.includes(v);
      if (multiple) return has ? cur.filter((x) => x !== v) : [...cur, v];
      return has ? [] : [v];
    });
    page = 0;
  }

  // ---- sort state (reactive) ----
  let sortCol = initialSort?.col;
  let sortDir = initialSort?.dir ?? 'desc';
  let page = 0;
  function headerClick(id) {
    if (sortCol === id) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    else { sortCol = id; sortDir = 'asc'; }
    page = 0;
  }

  const rowsNum = typeof rows === 'string' ? parseInt(rows) : rows;

  function sortRows(r, col, dir) {
    if (!col) return r;
    const out = [...r].sort((a, b) => {
      const x = a[col], y = b[col];
      if (x == null && y == null) return 0;
      if (x == null) return 1;
      if (y == null) return -1;
      if (typeof x === 'number' && typeof y === 'number') return x - y;
      return String(x).localeCompare(String(y), undefined, { numeric: true });
    });
    return dir === 'desc' ? out.reverse() : out;
  }

  function fmtCell(val, fmt) {
    // pct with no value -> "-"
    if (fmt === 'pct') {
      if (val == null || val === '' || Number.isNaN(Number(val))) return '-';
      return (Number(val) * 100).toLocaleString('en-US', { maximumFractionDigits: 0 }) + '%';
    }
    if (val == null || val === '') return '';
    if (fmt === 'num') return Number(val).toLocaleString('en-US', { maximumFractionDigits: 0 });
    if (fmt === 'delta') {
      const n = Number(val);
      // zero diff -> "0 –" (en dash, matching Evidence's neutral delta)
      if (n === 0) return '0 –';
      const arrow = n > 0 ? '▲' : '▼';
      return `${arrow} ${Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
    }
    return val;
  }
  function deltaClass(val, downIsGood) {
    const n = Number(val);
    if (n === 0) return 'delta-zero';   // explicit black, not inherited muted
    const good = downIsGood ? n < 0 : n > 0;
    return good ? 'delta-good' : 'delta-bad';
  }
  function resolveColumns(r) {
    if (columns && columns.length) return columns;
    if (!r || !r.length) return [];
    return Object.keys(r[0]).map((id) => ({ id, title: id }));
  }
  const isNumericFmt = (f) => f === 'num' || f === 'pct' || f === 'delta';
</script>

<QueryLoad {data} let:loaded>
  <!-- reactive: recompute whenever loaded, sortCol, sortDir, selection, or page change -->
  {@const cols = resolveColumns(loaded)}
  {@const base = (collapseOnSelect && $selected.length > 0)
      ? loaded.filter((r) => $selected.includes(r[valueCol]))
      : loaded}
  {@const sorted = sortRows(base, sortCol, sortDir)}
  {@const total = sorted.length}
  {@const pageCount = Math.max(1, Math.ceil(total / rowsNum))}
  {@const safePage = Math.min(page, pageCount - 1)}
  {@const pageRows = sorted.slice(safePage * rowsNum, safePage * rowsNum + rowsNum)}
  <div class="selectable-table text-xs">
    <table class="w-full border-collapse">
      <thead>
        <tr>
          {#each cols as c}
            <th
              class="font-semibold py-1 pr-3 cursor-pointer select-none whitespace-nowrap header-cell"
              style={isNumericFmt(c.fmt) || c.align === 'right' ? 'text-align:right' : 'text-align:left'}
              on:click={() => headerClick(c.id)}
            >
              <span class="hdr-inner">
                {c.title ?? c.id}{#if sortCol === c.id}<svg class="sort-chev" viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{#if sortDir === 'asc'}<path d="M6 15l6-6 6 6"/>{:else}<path d="M6 9l6 6 6-6"/>{/if}</svg>{/if}
              </span>
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each pageRows as row, i (row[valueCol])}
          <tr
            class="cursor-pointer row"
            class:shade={rowShading && i % 2 === 1}
            class:is-selected={$selected.includes(row[valueCol])}
            on:click={() => toggle(row)}
            role="button" tabindex="0"
            on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggle(row)}
          >
            {#each cols as c}
              <td
                class="py-1 pr-3 align-top {c.fmt === 'delta' ? deltaClass(row[c.id], c.downIsGood) : ''}"
                style={isNumericFmt(c.fmt) || c.align === 'right' ? 'text-align:right' : ''}
              >
                {fmtCell(row[c.id], c.fmt)}
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>

    <div class="flex items-center justify-between pt-2 text-base-content-muted footer">
      <span>
        {#if $selected.length > 0}
          <button class="link-btn" on:click={() => selected.set([])}>Show all intersections</button>
        {:else}
          {total.toLocaleString('en-US')} intersections
        {/if}
      </span>
      {#if pageCount > 1 && !(collapseOnSelect && $selected.length > 0)}
        <span class="flex items-center gap-2">
          <button class="pg" disabled={safePage === 0} on:click={() => (page = Math.max(0, safePage - 1))}>‹ Prev</button>
          <span>Page {safePage + 1} / {pageCount}</span>
          <button class="pg" disabled={safePage >= pageCount - 1} on:click={() => (page = Math.min(pageCount - 1, safePage + 1))}>Next ›</button>
        </span>
      {/if}
    </div>
  </div>
</QueryLoad>

<style>
  /* Match Evidence's DataTable: 9.5pt, ui font, tabular numerals. */
  .selectable-table :global(table) {
    font-size: 9.5pt;
    font-family: var(--ui-font-family);
    font-variant-numeric: tabular-nums;
    color: var(--base-content);
  }
  .selectable-table :global(thead tr) {
    border-bottom: 1px solid var(--base-content-muted, #94a3b8);
  }
  /* thin gray divider, matching border-base-content-muted/20 */
  .selectable-table :global(tbody tr.row) {
    border-bottom: 1px solid color-mix(in srgb, var(--base-content-muted, #94a3b8) 20%, transparent);
  }
  /* Evidence shades odd data rows with base-200 */
  .selectable-table :global(tbody tr.shade) { background: var(--base-200, #e5e7eb); }
  .selectable-table :global(tbody tr:hover) { background: var(--base-200, #e5e7eb); }
  .selectable-table :global(tbody tr.is-selected),
  .selectable-table :global(tbody tr.is-selected:hover) { background: var(--primary, #2563eb); color: #fff; }
  .selectable-table :global(td.delta-good) { color: #16a34a; }
  .selectable-table :global(td.delta-bad)  { color: #dc2626; }
  .selectable-table :global(td.delta-zero) { color: var(--base-content, #1f2937); }
  .selectable-table :global(tr.is-selected td.delta-good),
  .selectable-table :global(tr.is-selected td.delta-bad) { color: #fff; }

  /* Evidence shows its chevron only on the sorted column (Tabler ChevronUp/Down, 10px). */
  .selectable-table :global(.sort-chev) {
    display: inline-block; margin-left: 3px; margin-bottom: 1px;
    vertical-align: middle;
    pointer-events: none;
  }

  .selectable-table :global(.link-btn),
  .selectable-table :global(.pg) { text-decoration: underline; cursor: pointer; }
  .selectable-table :global(.pg:disabled) { opacity: 0.4; cursor: default; text-decoration: none; }
  .selectable-table :global(.footer) { font-size: 11px; }
</style>
