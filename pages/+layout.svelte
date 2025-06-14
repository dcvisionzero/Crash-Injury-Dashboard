<script>
	import '@evidence-dev/tailwind/fonts.css';
	import '../app.css';
	import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
	export let data;
</script>

<EvidenceDefaultLayout {data} logo="https://app.box.com/shared/static/gumr231kd3x35lrvkl54qirbphvsnkkx.png" builtWithEvidence={false} fullWidth={true} hideTOC={true}>
	<slot slot="content" />
</EvidenceDefaultLayout>
