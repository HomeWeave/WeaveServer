function createView(namespace, target, params) {
	
	var rawHtml = null;
	var compiledHtml = null;
	var processedHtml = null;
	var args = null;
	var innerViews = {};

	var socket = io.connect('http://' + document.domain + ':' + location.port + namespace, {
		//transports: ['websocket']
		rememberTransport: false
	});

	socket.on('connect', function(data) {
		socket.emit('request_view', {});
	});
	
	socket.on('view', function(data) {
		if (data.args) {
			args = data.args;
		}
		if (data.innerViews) {
			Object.keys(data.innerViews).forEach(function (name) {
				var view = data.innerViews[name];
				var namespace = view.namespace;
				var randomId = "innerview-" + Math.random().toString(36).substring(2);
				var tempHtml = '<div id="' + randomId + '"></div>';
				args[name] = tempHtml;
				
				var loadInner = function(html) {
					$("#" + randomId).html(html);
				}

				var viewObj = createView(namespace, loadInner, {});
				viewObj.render();
				innerViews[name] = viewObj;

			});
		}
		if (data.html) {
			rawHtml = data.html;
			compiledHtml = Handlebars.compile(data.html);
		}
		if (compiledHtml) {
			processedHtml = compiledHtml(args);
		}
		updateView();
	});

	function requestView() {
		socket.emit("request_view", {});
	}

	function updateView() {
		if (processedHtml != null && target != null) {
			if (typeof target === 'string') {
				$(target).html(processedHtml);
			}
			else if (typeof target === 'function') {
				target(processedHtml);
			}
		}
	}

	return {
		render: function() {
			requestView()
		}
	};

}