export default {
  init() {
    // JavaScript to be fired on all pages
    // Load Lightbox
    $(document).on('click', '[data-toggle="lightbox"]', function(event) {
      event.preventDefault();
      $(this).ekkoLightbox();
    });

    // Used for sorting amounts in the payment tables. It filters the amounts from the HTML, replaces the comma with a dot and removes white space (thousand separators).
    $('.payment-table').bootstrapTable(
      {
        search: true,
        pagination: true,
        stickyHeader: true,
        classes: 'table'
      }
    );

    // We need JavaScript to set the rounded border of the last visible element in a tr
    $('.payment-table tr').find('td:not(.d-none):last').css(
      {
        'border-right-style': 'solid',
        'border-bottom-right-radius': '35px',
        'border-top-right-radius': '35px'
      }
    )
  },
  finalize() {
    // JavaScript to be fired on all pages, after page specific JS is fired
  },
};
