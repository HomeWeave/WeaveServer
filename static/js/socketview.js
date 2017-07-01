function createView(namespace, selector, params) {
	
	var targetSelector = selector;
	var html = null;
	var args = null;

	var socket = io.connect('http://' + document.domain + ':' + location.port + namespace, {});

	socket.on('connect', function(data) {
		socket.emit('request_view', {});
	});
	
	socket.on('view', function(data) {
		if (data.html) {
			html = Handlebars.compile(data.html);
		}
		if (data.args) {
			args = data.args;
		}
		updateView();
	});

	function requestView() {
		socket.emit("request_view", {});
	}

	function updateView() {
		if (targetSelector != null && html != null) {
			var substHtml = html(args);
			$(targetSelector).html(substHtml);
		}
	}

	return {
		render: function() {
			requestView()
		}
	};

}