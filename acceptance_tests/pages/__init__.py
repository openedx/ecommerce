def submit_lms_login_form(page, email, password):
    """ Fill out and submit the LMS login form. """
    page.q(css='input#login-email').fill(email)
    page.q(css='input#login-password').fill(password)
    page.q(css='button.login-button').click()
