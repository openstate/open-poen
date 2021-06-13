export default {
  init() {
    // JavaScript to be fired on the Project and Subproject pages as you can
    // add new transactions there
    window.set_category = function(selected) {
      $('#new_payment_form-category_id').html(function() {
          var categories_html = '';
          $.each(categories_dict[selected.value], function(i) {
            categories_html += '<option value="' + categories_dict[selected.value][i][0] + '">' + categories_dict[selected.value][i][1] + '</option>';
          });
          return categories_html;
      });
    }
  },
  finalize() {
    // JavaScript to be fired on the home page, after the init JS
  },
};
