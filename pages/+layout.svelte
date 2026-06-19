<script>
	import '@evidence-dev/tailwind/fonts.css';
	import '../app.css';
	import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
	export let data;
</script>

<a class="vz-mobile-logo" href="/Crash-Injury-Dashboard/" aria-label="Home">
	<img src="https://app.box.com/shared/static/gumr231kd3x35lrvkl54qirbphvsnkkx.png" alt="Home" />
</a>

<EvidenceDefaultLayout {data} logo="https://app.box.com/shared/static/gumr231kd3x35lrvkl54qirbphvsnkkx.png" builtWithEvidence={false} fullWidth={true} hideTOC={true} githubRepo={"https://github.com/dcvisionzero/Crash-Injury-Dashboard"}>
	<slot slot="content" />
</EvidenceDefaultLayout>

<style>
	.vz-mobile-logo {
		display: none;
	}

	@media (max-width: 767.98px) {
		.vz-mobile-logo {
			position: fixed;
			top: 0;
			left: 50%;
			transform: translateX(-50%);
			height: 3rem;
			display: flex;
			align-items: center;
			z-index: 50;
		}
	}

	.vz-mobile-logo img {
		height: 1.25rem;
		width: auto;
	}

	@media print {
		.vz-mobile-logo {
			display: none;
		}
	}
</style>
