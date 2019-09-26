// Import external dependencies
import 'jquery';
import 'bootstrap';
import 'bootstrap-table';
import 'bootstrap-table/dist/extensions/sticky-header/bootstrap-table-sticky-header.min.js';
import 'bootstrap-table/dist/extensions/mobile/bootstrap-table-mobile.min.js';

// Import local dependencies
import Router from './util/Router';
import common from './routes/common';
import home from './routes/home';

// Import the needed Font Awesome functionality
import { config, library, dom } from '@fortawesome/fontawesome-svg-core';
// Import required icons
import { faArrowRight, faBars } from '@fortawesome/free-solid-svg-icons';
import { faEnvelope } from '@fortawesome/free-regular-svg-icons';
import { faGithub } from '@fortawesome/free-brands-svg-icons';

// Allow usage in pseudo elements
config.searchPseudoElements=true;

// Add the imported icons to the library
library.add(faArrowRight, faEnvelope, faGithub, faBars);

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
$(document).ready(() => routes.loadEvents());
