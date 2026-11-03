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
  export let columns = undefined;         // [{id,title?,fmt?,align?,downIsGood?,colorscale?,sub?}]
                                          // sub: id of a column shown as a small second line
                                          //      under this cell (e.g. a ward under a hexagon)
  export let initialSort = undefined;     // {col,dir}
  export let rows = 10;                    // rows per page
  export let rowShading = false;
  export let collapseOnSelect = false;    // when a row is selected, show only it
  export let wrapTitles = false;          // allow header titles to wrap to multiple lines
  export let itemLabel = 'intersections'; // noun used in the footer (count and "Show all")

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

  // ---- colorscale: shade cells by value, matching DataTable's contentType=colorscale ----
  // Column options:
  //   colorscale: true            -> DEFAULT_SCALE (mirror of theme.colorScales.default
  //                                  in evidence.config.yaml; Evidence does not export
  //                                  its theme store, so the colors live here)
  //   colorscale: ['#hex', ...]   -> explicit stops (2 or more), low to high
  //   colorMin / colorMax         -> fix the domain ends (e.g. colorMin: 0 to match a
  //                                  map using min=0); otherwise the data min/max
  // Interpolation is linear RGB, the same as chroma.scale() inside DataTable, and the
  // text color uses DataTable's contrast rule. The domain spans ALL loaded rows, not
  // just the current page, so a shade means the same thing on every page.
  const DEFAULT_SCALE = ['#ADD8E6', '#00008B'];
  const TEXT_DARK = '#09090b';   // theme base-content (light)
  const TEXT_LIGHT = '#ffffff';  // theme base-100 (light)

  const hexToRgb = (h) => {
    const s = h.replace('#', '');
    const f = s.length === 3 ? s.split('').map((x) => x + x).join('') : s;
    return [0, 2, 4].map((i) => parseInt(f.slice(i, i + 2), 16));
  };
  const rgbToHex = (c) => '#' + c.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');
  function interpolate(stops, t) {
    const rgb = stops.map(hexToRgb);
    const seg = Math.min(rgb.length - 2, Math.floor(t * (rgb.length - 1)));
    const local = t * (rgb.length - 1) - seg;
    return rgb[seg].map((v, i) => v + (rgb[seg + 1][i] - v) * local);
  }
  // WCAG relative luminance / contrast, as chroma.contrast computes them
  function luminance(rgb) {
    const [r, g, b] = rgb.map((v) => {
      const s = v / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }
  function contrast(a, b) {
    const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (l1 + 0.05) / (l2 + 0.05);
  }

  function colorRanges(r, cols) {
    const out = {};
    for (const c of cols) {
      if (!c.colorscale) continue;
      const vals = r.map((x) => Number(x[c.id])).filter((v) => Number.isFinite(v));
      if (!vals.length) { out[c.id] = null; continue; }
      out[c.id] = {
        min: c.colorMin ?? Math.min(...vals),
        max: c.colorMax ?? Math.max(...vals),
        stops: Array.isArray(c.colorscale) ? c.colorscale : DEFAULT_SCALE
      };
    }
    return out;
  }
  function colorStyle(val, range) {
    const n = Number(val);
    if (!range || !Number.isFinite(n) || range.max === range.min) return '';
    const t = Math.min(1, Math.max(0, (n - range.min) / (range.max - range.min)));
    const bg = interpolate(range.stops, t);
    const fg = contrast(bg, hexToRgb(TEXT_DARK)) < contrast(bg, hexToRgb(TEXT_LIGHT)) + 0.5
      ? TEXT_LIGHT : TEXT_DARK;
    return `background:${rgbToHex(bg)};color:${fg};`;
  }
</script>

<QueryLoad {data} let:loaded>
  <!-- reactive: recompute whenever loaded, sortCol, sortDir, selection, or page change -->
  {@const cols = resolveColumns(loaded)}
  {@const ranges = colorRanges(loaded, cols)}
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
              class="font-semibold py-1 pr-3 cursor-pointer select-none header-cell {wrapTitles ? '' : 'whitespace-nowrap'}"
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
                style={(isNumericFmt(c.fmt) || c.align === 'right' ? 'text-align:right;' : '')
                  + (c.colorscale ? colorStyle(row[c.id], ranges[c.id]) : '')}
              >
                {fmtCell(row[c.id], c.fmt)}
                {#if c.sub && row[c.sub] != null && row[c.sub] !== ''}
                  <span class="sub-line">{row[c.sub]}</span>
                {/if}
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>

    <div class="flex items-center justify-between pt-2 text-base-content-muted footer">
      <span>
        {#if $selected.length > 0}
          <button class="link-btn" on:click={() => selected.set([])}>Show all {itemLabel}</button>
        {:else}
          {total.toLocaleString('en-US')} {itemLabel}
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
  /* second line under a cell (column option `sub`); opacity keeps it readable on the selected row */
  .selectable-table :global(.sub-line) { display: block; font-size: 8.5pt; opacity: 0.7; line-height: 1.2; }

  /* Evidence shows its chevron only on the sorted column (Tabler ChevronUp/Down, 10px). */
  .selectable-table :global(.sort-chev) {
    display: inline-block; margin-left: 3px; margin-bottom: 1px;
    vertical-align: middle;
    pointer-events: none;
  }
  /* keep multi-line headers top-aligned so columns line up when titles wrap */
  .selectable-table :global(thead th) { vertical-align: top; }

  .selectable-table :global(.link-btn),
  .selectable-table :global(.pg) { text-decoration: underline; cursor: pointer; }
  .selectable-table :global(.pg:disabled) { opacity: 0.4; cursor: default; text-decoration: none; }
  .selectable-table :global(.footer) { font-size: 11px; }
</style>
