define([], function() {
    var callApi = function(url, data) {
        return fetch(url, {
            method: 'POST',
            body: data
        }).then(function(response) {
            if (!response.ok) {
                throw new Error('HTTP error ' + response.status);
            }
            return response.json();
        });
    };

    var callJsonApi = function(url, payload) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(function(response) {
            if (!response.ok) {
                throw new Error('HTTP error ' + response.status);
            }
            return response.json();
        });
    };

    var fetchJson = function(url) {
        return fetch(url).then(function(response) {
            if (!response.ok) {
                throw new Error('HTTP error ' + response.status);
            }
            return response.json();
        });
    };

    return {
        callApi: callApi,
        callJsonApi: callJsonApi,
        fetchJson: fetchJson
    };
});
