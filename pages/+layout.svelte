<script>
	import '@evidence-dev/tailwind/fonts.css';
	import '../app.css';
	import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
	export let data;
</script>

<!-- Mobile-only centered logo. The default header hides its logo below md (768px),
     so this overlays the same fixed bar on small screens. -->
<a class="vz-mobile-logo" href="/Crash-Injury-Dashboard/" aria-label="Home">
	<img src="https://app.box.com/shared/static/gumr231kd3x35lrvkl54qirbphvsnkkx.png" alt="Home" />
</a>

<EvidenceDefaultLayout {data} logo="https://app.box.com/shared/static/gumr231kd3x35lrvkl54qirbphvsnkkx.png" builtWithEvidence=false fullWidth=true>
	<slot slot="content" />
</EvidenceDefaultLayout>

<style>
	/* Hidden by default (desktop shows the built-in logo). */
	.vz-mobile-logo {
		display: none;
	}

	/* Show only below Evidence's md breakpoint, centered in the 48px header bar. */
	@media (max-width: 767.98px) {
		.vz-mobile-logo {
			position: fixed;
			top: 0;
			left: 50%;
			transform: translateX(-50%);
			height: 3rem; /* matches header h-12 */
			display: flex;
			align-items: center;
			z-index: 50; /* above the header's z-40 */
		}
	}

	.vz-mobile-logo img {
		height: 1.25rem; /* matches desktop logo h-5 (20px) */
		width: auto;
	}

	@media print {
		.vz-mobile-logo {
			display: none;
		}
	}
</style>
