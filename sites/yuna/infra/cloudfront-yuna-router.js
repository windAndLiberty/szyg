function handler(event) {
  var request = event.request;
  var uri = request.uri;

  // The distribution-wide clean URL function would otherwise rewrite
  // /yuna to /yuna.html. Route the application root to its real index file.
  if (uri === '/yuna') {
    request.uri = '/yuna/index.html';
  } else if (uri.endsWith('/')) {
    request.uri = uri + 'index.html';
  } else if (!uri.includes('.')) {
    request.uri = uri + '.html';
  }

  return request;
}
