# Adobe Experience Manager: where the concierge's content comes from

The *Guest Services Playbook* the concierge answers from - check-in, Princess
Upgrade, packages, dining, Princess Cays, spa, policies - is authored in AEM
as **Content Fragments** (model `guest-services-playbook-entry`: question,
answer, keywords, effective dates) and published through AEM's GraphQL API.

    POST https://<aem-publish>/graphql/execute.json/princess/guest-services-playbook
    (persisted query `guest-services-playbook.graphql`)

Every morning, after the Real-Time CDP export loads, the backend fetches the
published entries, renders today's playbook document and publishes it to the
AOM Knowledge Base; the concierge's RAG application is re-scoped to that
document. Offer copy (upgrade, dining, spa cards) uses the same fragments.

Without an AEM endpoint configured (`AEM_GRAPHQL_ENDPOINT`), the backend
serves the bundled fragments in `backend/app/knowledge.py` (`mode: mock`) -
same shape, same content model.
