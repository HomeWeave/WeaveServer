$(document).ready(function() {
    var statusRequest = $.ajax({
        url: "/api/status",
        dataType: "json"
    });

    $.when(statusRequest).then(function(statusResponse) {
        var smallCards = [
            {
                cardType: 'success',
                icon: {material: 'build'},
                title: 'Version',
                content: statusResponse.version,
                footer: []
            },
            {
                cardType: 'warning',
                icon: {material: 'dns'},
                title: 'Rules',
                content: statusResponse.rules + " rules active",
                footer: []
            },
            {
                cardType: 'info',
                icon: {material: 'developer_board'},
                title: 'Plugins',
                content: statusResponse.plugins + " loaded",
                footer: []
            },
        ];
        var mediumCards = [
            {
                html: "",
                cardType: 'success',
                cardTitle: "Title1",
                cardContent: [
                    {material: 'face', text: "Point1"},
                    {material: 'content_copy', text: "Point2"}
                ],
                footer: [
                    {
                        url: '#',
                        iconName: '',
                        message: 'Get More Space'
                    }
                ]
            }
        ];

        var smallCard = SmallCard();
        var mediumCard = MediumCard();

        $('.content .weave-small-cards-row').html($.map(smallCards, smallCard.html).join(""));
        // $('.content .weave-medium-cards-row').html($.map(mediumCards, mediumCard.html).join(""));
    });
});