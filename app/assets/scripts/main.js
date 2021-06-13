// Import external dependencies
import 'jquery';
import 'bootstrap';
import 'ekko-lightbox/dist/ekko-lightbox.min.js';
import 'bootstrap-table';
import 'bootstrap-table/dist/locale/bootstrap-table-nl-NL.min.js';
import 'bootstrap-table/dist/extensions/sticky-header/bootstrap-table-sticky-header.min.js';
import 'bootstrap-table/dist/extensions/mobile/bootstrap-table-mobile.min.js';
import 'tableexport.jquery.plugin/tableExport.min.js';
import 'bootstrap-table/dist/extensions/export/bootstrap-table-export.min.js';
import naturalSort from 'javascript-natural-sort';

// Import local dependencies
import Router from './util/Router';
import common from './routes/common';
import home from './routes/home';
import transaction from './routes/transaction';

// Import the needed Font Awesome functionality
import { config, library, dom } from '@fortawesome/fontawesome-svg-core';
// Import required icons
import { faBars, faChevronDown, faFile, faCamera, faDownload } from '@fortawesome/free-solid-svg-icons';

// Add the imported icons to the library
library.add(faBars, faChevronDown, faFile, faCamera, faDownload);

// Tell FontAwesome to watch the DOM and add the SVGs when it detects icon markup
dom.watch();

// Populate Router instance with DOM routes
const routes = new Router({
  // All pages
  common,
  // Home page
  home,
  // Project and Subproject pages can add new transactions
  transaction,
});

// Load events
$(document).ready(() => routes.loadEvents());

// Used for sorting amounts in the payment tables. It filters the amounts from the HTML, replaces the comma with a dot and removes white space (thousand separators).
window.customSort = function(a, b) {
  var aa = a.match('[^>]*>(.*)</h1>')[1].replace(',', '.').replace(/\s/g, '');
  var bb = b.match('[^>]*>(.*)</h1>')[1].replace(',', '.').replace(/\s/g, '');
  return naturalSort(aa, bb);
};

// Format detail view of payment table row
window.detailFormatter = function(index, row) {
  var id = row[0].match(/>\s+(\d+)\s+<\/div>/)[1]
  return $('#detail-' + id).html()
}
