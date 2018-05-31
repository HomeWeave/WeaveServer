function loadSystemCards(data) {
    var smallCards = [
        {
            cardType: 'success',
            icon: {material: 'build'},
            title: 'Version',
            content: data.version,
            footer: [
                {
                    icon: {material: 'build'},
                    url: "#",
                    message: "Test"
                }
            ]
        },
        {
            cardType: 'warning',
            icon: {material: 'dns'},
            title: 'Rules',
            content: data.rules + " active",
            footer: []
        },
        {
            cardType: 'info',
            icon: {material: 'developer_board'},
            title: 'Plugins',
            content: data.plugins + " loaded",
            footer: []
        },
    ];
    var cards = smallCards.forEach(function(data) {
        var card = SmallCard('.content .weave-small-cards-row');
        card.load(data);
        return card;
    });
}

function loadComponents(components) {
    components.forEach(function(component) {
        var card = MediumCard('.content .weave-medium-cards-row');
        card.load(component);
    });
}

$(document).ready(function() {
    registerComponents();
    var statusRequest = $.ajax({
        url: "/api/status",
        dataType: "json"
    });

    $.when(statusRequest).then(function(statusResponse) {
        loadSystemCards(statusResponse);
        loadComponents(statusResponse.components);
    });
});