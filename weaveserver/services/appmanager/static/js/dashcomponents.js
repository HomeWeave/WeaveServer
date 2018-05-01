function Context() {
	var variables = {};

	return {
		get: function(val) { return variables[val]; },
		set: function(key, val) {
			variables[key] = val;
		}
	}
}

function ActionEvaluator(context) {
	function rpc(data) {
		
	}

	var handlers = {rpc: rpc};
	return {
		evaluate: function(action) {
			var handler = handlers[action.type];
			if (handler === undefined) { return; }

			handler(action);
		}
	}
}

function GenericTemplate(selector) {
    var source = $(selector).html();
    var template = Handlebars.compile(source);
    return {
        html: function(data) {
            return template(data);
        }
    }
}

function GenericCard(template, selector) {
	var template = GenericTemplate(template);
	var context = Context();

	return {
		load: function(data) {
			var loadFuncs = (data["actions"] || {})["$load"] || [];
			loadFuncs.forEach(function(action) {
				fireAction(action, context);
			});
			$(selector).append(template.html(data));
		}
    }
}

function SmallCard() {
    return GenericTemplate("#template-small-card")
}

function MediumCard(selector) {
    return GenericCard("#template-medium-card", selector);
}
