// Import external dependencies
import 'jquery';
import 'bootstrap';

// Import local dependencies
import Router from './util/Router';
import common from './routes/common';
import home from './routes/home';

// Import the needed Font Awesome functionality
import { config, library, dom } from '@fortawesome/fontawesome-svg-core';
// Import required icons
import { faArrowRight } from '@fortawesome/free-solid-svg-icons';
import { faEnvelope } from '@fortawesome/free-regular-svg-icons';
import { faGithub } from '@fortawesome/free-brands-svg-icons';

// Allow usage in pseudo elements
config.searchPseudoElements=true;

// Add the imported icons to the library
library.add(faArrowRight, faEnvelope, faGithub);

// Tell FontAwesome to watch the DOM and add the SVGs when it detects icon markup
dom.watch();

// Populate Router instance with DOM routes
const routes = new Router({
  // All pages
  common,
  // Home page
  home,
});

// Load events
jQuery(document).ready(() => routes.loadEvents());
