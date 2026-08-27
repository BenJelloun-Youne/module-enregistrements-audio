/**
 * À ajouter dans le tableau de navigation admin (sidebar-nav.js du SaaS cible).
 * Rôles : admin uniquement, comme sur Concentrix.
 */
{
    title: 'Enregistrements',
    items: [
        {
            id: 'navEnregistrements',
            label: 'Enregistrements et relances',
            icon: 'mic',
            href: '/pages/enregistrements-relances.html?v=1',
            roles: ['admin']
        },
        {
            id: 'navCriteresAudio',
            label: "Critères d'analyse audio",
            icon: 'sliders',
            href: '/pages/criteres-analyse-audio.html?v=1',
            roles: ['admin']
        }
    ]
}
