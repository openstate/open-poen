// Import external dependencies
import * as d3 from 'd3';
import 'jquery';
import 'bootstrap';
import 'ekko-lightbox/dist/ekko-lightbox.min.js';
import 'bootstrap-table';
import 'bootstrap-table/dist/locale/bootstrap-table-nl-NL.min.js';
import 'bootstrap-table/dist/extensions/sticky-header/bootstrap-table-sticky-header.min.js';
import 'bootstrap-table/dist/extensions/mobile/bootstrap-table-mobile.min.js';
import 'tableexport.jquery.plugin/tableExport.min.js';
import 'bootstrap-table/dist/extensions/export/bootstrap-table-export.min.js';
import 'bootstrap-table/dist/extensions/cookie/bootstrap-table-cookie.min.js';
import naturalSort from 'javascript-natural-sort';
import moment from 'moment';

// Import local dependencies
import Router from './util/Router';
import common from './routes/common';
import home from './routes/home';
import transaction from './routes/transaction';

// Import the needed Font Awesome functionality
import { config, library, dom } from '@fortawesome/fontawesome-svg-core';
// Import required icons
import { faBars, faChevronDown, faFile, faCamera, faDownload, faReceipt } from '@fortawesome/free-solid-svg-icons';

// Add the imported icons to the library
library.add(faBars, faChevronDown, faFile, faCamera, faDownload, faReceipt);

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

// Needed to sort dates in payment tables
window.sortByDate = function(a, b) {
  var aValue = moment(a, "DD-MM-'YY").format('YYYYMMDD');
  if (a === '' || a === null) { aValue = 0; }

  var bValue = moment(b, "DD-MM-'YY").format('YYYYMMDD');
  if (b === '' || b === null) { bValue = 0; }

  return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
}

// Format detail view of payment table row
window.detailFormatter = function(index, row) {
  var id = row[0].match(/>\s+(\d+)\s+<\/div>/)[1]
  return $('#detail-' + id).html()
}

// Create a donut with of the spent percentage
window.donut = function(thisObj) {
  // Clear HTML, otherwise you generate more donuts when resizing the window
  $(thisObj).html('');

  // Get the percentage from this custom attribute we set
  var uses = parseInt($(thisObj).attr('data-percentage'));

  var chart = d3.select(thisObj);

  var width = $(thisObj).width();

  var height = width;

  var radius = Math.min(width, height) / 2;

  var color = d3.scale.ordinal()
    .range(["#0096dc", "#c60060"]);

  var arc = d3.svg.arc()
    .outerRadius(radius)
    .innerRadius(radius - width / 6);

  var pie = d3.layout.pie()
    .value(function (d) {
    return d.value;
  }).sort(null);

  chart = chart
    .append('svg')
    .attr("width", width)
    .attr("height", height)
    .append("g")
    .attr("transform", "translate(" + (width / 2) + "," + (height / 2) + ")");

  // just abort and leave it blank if something's wrong
  // (instead of showing "NaN%" visually)
  if (isNaN(uses))
    return;

  var pie_uses = uses;
  if (uses > 100) {
    pie_uses = 100;
  }
  var pie_data = [
    {status: 'active', value: pie_uses},
    {status: 'inactive', value: (100 - pie_uses)},
  ]

  var g = chart.selectAll(".arc")
    .data(pie(pie_data))
    .enter().append("g")
    .attr("class", "arc");

  g.append("path")
    .style("fill", function(d) {
    return color(d.data.status);
  })
    .transition().delay(function(d, i) {
    return i *400;
  }).duration(400)
    .attrTween('d', function(d) {
    var i = d3.interpolate(d.startAngle+ 0.1, d.endAngle);
    return function(t) {
      d.endAngle = i(t);
      return arc(d);
    }
  });

  // Add text inside the donut
  g.append("text")
    .attr("text-anchor", "middle")
    .attr("font-size", "10")
    .attr("class", "total-type")
    .attr("dy", "-0.2em")
    .attr("fill", "#000000")
    .text(function(d){
      return "besteed";
  });

  // Add percentage inside the donut
  g.append("text")
    .attr("text-anchor", "middle")
    .attr("font-size", "10")
    .attr("class", "total-type")
    .attr("class", "total-value")
    .attr("dy", "1.0em")
    .attr("fill", "#000000")
    .text(function(d){
      return "" + uses + "%";
  });
}

window.createDonuts = function() {
  $('.donut').each(function() {window.donut(this)});
}

createDonuts();
