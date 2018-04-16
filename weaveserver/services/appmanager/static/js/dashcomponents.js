function GenericTemplate(selector) {
    var source = $(selector).html();
    var template = Handlebars.compile(source);
    return {
        html: function(data) {
            return template(data);
        }
    }
}

function SmallCard() {
    return GenericTemplate("#template-small-card")
}

function MediumCard() {
    return GenericTemplate("#template-medium-card");
}
