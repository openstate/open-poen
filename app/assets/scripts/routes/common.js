export default {
  init() {
    // JavaScript to be fired on all pages
    $('.payment-table').bootstrapTable(
        {
            search: true,
            pagination: true,
            stickyHeader: true,
            mobileResponsive: true
        }
    );
  },
  finalize() {
    // JavaScript to be fired on all pages, after page specific JS is fired
  },
};
