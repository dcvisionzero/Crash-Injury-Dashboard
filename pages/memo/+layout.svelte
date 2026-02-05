<script>
    import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
    export let data;
  </script>
  
  <EvidenceDefaultLayout {data} hideHeader={true} hideBreadcrumbs={true} builtWithEvidence={false} hideSidebar={true}>
	<slot slot="content" />
</EvidenceDefaultLayout>
  