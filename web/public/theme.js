try {
  var theme = window.localStorage.getItem('wikipulse-theme')
  if (theme === 'light' || theme === 'dark') {
    document.documentElement.dataset.theme = theme
  }
} catch (error) {
  void error
}
