
$(document).ready(function() {
	var socket = io.connect('http://' + document.domain + ':' + location.port + "/navigation");

	socket.on('view', function(data) {
		console.log("WS" + JSON.stringify(data));
		$("#page-wrapper").html(data.html);
	});

	socket.emit('request_view', {});
})