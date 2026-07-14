document.addEventListener("DOMContentLoaded", function () {
    initAutoHideMessages();
    initAmountValidation();
    initPinValidation();
    initConfirmActions();
    initPasswordToggle();
    initProfilePreview();
    initTableSearch();
    initSessionActivity();
    initFormProtection();
});


// ==========================================
// AUTO HIDE ALERT / MESSAGE
// ==========================================

function initAutoHideMessages() {

    const messages = document.querySelectorAll(
        ".alert, .message"
    );

    messages.forEach(function (message) {

        setTimeout(function () {

            message.style.transition = "0.4s";
            message.style.opacity = "0";
            message.style.transform =
                "translateY(-10px)";

            setTimeout(function () {

                message.remove();

            }, 400);

        }, 5000);

    });

}


// ==========================================
// AMOUNT VALIDATION
// ==========================================

function initAmountValidation() {

    const amountInputs = document.querySelectorAll(
        'input[name="amount"], ' +
        'input[name="principal"], ' +
        'input[name="balance"], ' +
        'input[name="rate"], ' +
        'input[name="time"]'
    );

    amountInputs.forEach(function (input) {

        input.addEventListener(
            "input",
            function () {

                const value = Number(
                    this.value
                );

                if (
                    this.value !== ""
                    && value < 0
                ) {

                    this.value = "";

                    showMessage(
                        "Negative value is not allowed.",
                        "error"
                    );

                }

            }
        );

    });

}


// ==========================================
// PIN VALIDATION
// ==========================================

function initPinValidation() {

    const pinInputs = document.querySelectorAll(
        'input[name="pin"], ' +
        'input[name="old_pin"], ' +
        'input[name="new_pin"], ' +
        'input[name="confirm_pin"]'
    );

    pinInputs.forEach(function (input) {

        input.addEventListener(
            "input",
            function () {

                this.value = this.value.replace(
                    /\D/g,
                    ""
                );

                if (this.value.length > 6) {

                    this.value = this.value.substring(
                        0,
                        6
                    );

                }

            }
        );

    });


    const newPin = document.querySelector(
        'input[name="new_pin"]'
    );

    const confirmPin = document.querySelector(
        'input[name="confirm_pin"]'
    );


    if (
        newPin
        && confirmPin
    ) {

        confirmPin.addEventListener(
            "input",
            function () {

                if (this.value === "") {

                    this.style.borderColor = "";

                    return;

                }

                if (
                    this.value
                    !== newPin.value
                ) {

                    this.style.borderColor =
                        "#dc2626";

                } else {

                    this.style.borderColor =
                        "#16a34a";

                }

            }
        );


        newPin.addEventListener(
            "input",
            function () {

                if (
                    confirmPin.value === ""
                ) {

                    return;

                }

                if (
                    confirmPin.value
                    !== newPin.value
                ) {

                    confirmPin.style.borderColor =
                        "#dc2626";

                } else {

                    confirmPin.style.borderColor =
                        "#16a34a";

                }

            }
        );

    }

}


// ==========================================
// CONFIRM DANGEROUS ACTIONS
// ==========================================

function initConfirmActions() {

    const deleteLinks = document.querySelectorAll(
        'a[href*="delete_user"]'
    );


    deleteLinks.forEach(function (link) {

        link.addEventListener(
            "click",
            function (event) {

                const confirmed = confirm(
                    "Are you sure you want to delete this user?"
                );

                if (!confirmed) {

                    event.preventDefault();

                }

            }
        );

    });


    const lockLinks = document.querySelectorAll(
        'a[href*="lock_user"]'
    );


    lockLinks.forEach(function (link) {

        link.addEventListener(
            "click",
            function (event) {

                const confirmed = confirm(
                    "Are you sure you want to lock this user?"
                );

                if (!confirmed) {

                    event.preventDefault();

                }

            }
        );

    });


    const withdrawForms = document.querySelectorAll(
        'form[action*="withdraw"], ' +
        'form[action*="fast_cash"]'
    );


    withdrawForms.forEach(function (form) {

        form.addEventListener(
            "submit",
            function (event) {

                const amount = form.querySelector(
                    'input[name="amount"]'
                );


                if (
                    amount
                    && Number(amount.value) > 0
                ) {

                    const confirmed = confirm(
                        "Confirm withdrawal of ₹"
                        + Number(
                            amount.value
                        ).toFixed(2)
                        + "?"
                    );


                    if (!confirmed) {

                        event.preventDefault();

                    }

                }

            }
        );

    });


    const transferForms = document.querySelectorAll(
        'form[action*="transfer"]'
    );


    transferForms.forEach(function (form) {

        form.addEventListener(
            "submit",
            function (event) {

                const amount = form.querySelector(
                    'input[name="amount"]'
                );

                const receiver = form.querySelector(
                    'input[name="receiver"], ' +
                    'input[name="receiver_card"]'
                );


                if (
                    amount
                    && receiver
                    && Number(amount.value) > 0
                    && receiver.value.trim() !== ""
                ) {

                    const confirmed = confirm(
                        "Transfer ₹"
                        + Number(
                            amount.value
                        ).toFixed(2)
                        + " to card "
                        + receiver.value
                        + "?"
                    );


                    if (!confirmed) {

                        event.preventDefault();

                    }

                }

            }
        );

    });


    const fdForms = document.querySelectorAll(
        'form[action*="fixed_deposit"]'
    );


    fdForms.forEach(function (form) {

        form.addEventListener(
            "submit",
            function (event) {

                const amount = form.querySelector(
                    'input[name="amount"]'
                );

                const months = form.querySelector(
                    'input[name="months"]'
                );


                if (
                    amount
                    && months
                    && Number(amount.value) > 0
                ) {

                    const confirmed = confirm(
                        "Create Fixed Deposit of ₹"
                        + Number(
                            amount.value
                        ).toFixed(2)
                        + " for "
                        + months.value
                        + " months?"
                    );


                    if (!confirmed) {

                        event.preventDefault();

                    }

                }

            }
        );

    });

}


// ==========================================
// SHOW / HIDE PIN
// ==========================================

function initPasswordToggle() {

    const passwordInputs = document.querySelectorAll(
        'input[type="password"]'
    );


    passwordInputs.forEach(function (input) {

        if (
            input.parentElement
            && input.parentElement.classList.contains(
                "pin-input-wrapper"
            )
        ) {

            return;

        }


        const wrapper = document.createElement(
            "div"
        );

        wrapper.className =
            "pin-input-wrapper";

        wrapper.style.position =
            "relative";


        input.parentNode.insertBefore(
            wrapper,
            input
        );

        wrapper.appendChild(
            input
        );


        const button = document.createElement(
            "button"
        );

        button.type = "button";

        button.innerText = "Show";

        button.className =
            "pin-toggle";

        button.style.position =
            "absolute";

        button.style.right =
            "10px";

        button.style.top =
            "50%";

        button.style.transform =
            "translateY(-50%)";

        button.style.width =
            "auto";

        button.style.padding =
            "6px 10px";

        button.style.fontSize =
            "12px";


        wrapper.appendChild(
            button
        );


        button.addEventListener(
            "click",
            function () {

                if (
                    input.type === "password"
                ) {

                    input.type = "text";

                    button.innerText = "Hide";

                } else {

                    input.type = "password";

                    button.innerText = "Show";

                }

            }
        );

    });

}


// ==========================================
// PROFILE IMAGE PREVIEW
// ==========================================

function initProfilePreview() {

    const profileInput = document.querySelector(
        'input[name="profile_pic"]'
    );


    if (!profileInput) {

        return;

    }


    profileInput.addEventListener(
        "change",
        function () {

            const file = this.files[0];


            if (!file) {

                return;

            }


            const allowedTypes = [
                "image/png",
                "image/jpeg",
                "image/webp"
            ];


            if (
                !allowedTypes.includes(
                    file.type
                )
            ) {

                showMessage(
                    "Only PNG, JPG, JPEG and WEBP images are allowed.",
                    "error"
                );

                this.value = "";

                return;

            }


            if (
                file.size
                > 2 * 1024 * 1024
            ) {

                showMessage(
                    "Profile image must be less than 2 MB.",
                    "error"
                );

                this.value = "";

                return;

            }


            const reader = new FileReader();


            reader.onload = function (event) {

                const preview = document.querySelector(
                    ".profile-image, .profile-pic"
                );


                if (preview) {

                    preview.src =
                        event.target.result;

                }

            };


            reader.readAsDataURL(
                file
            );

        }
    );

}


// ==========================================
// TABLE SEARCH
// ==========================================

function initTableSearch() {

    const searchInput = document.querySelector(
        "#tableSearch"
    );


    if (!searchInput) {

        return;

    }


    searchInput.addEventListener(
        "input",
        function () {

            const keyword = (
                this.value
                .trim()
                .toLowerCase()
            );


            const rows = document.querySelectorAll(
                "table tbody tr"
            );


            rows.forEach(function (row) {

                const text = (
                    row.innerText
                    .toLowerCase()
                );


                row.style.display = (
                    text.includes(keyword)
                    ? ""
                    : "none"
                );

            });

        }
    );

}


// ==========================================
// SESSION ACTIVITY WARNING
// ==========================================

function initSessionActivity() {

    let warningShown = false;


    setTimeout(function () {

        if (!warningShown) {

            warningShown = true;


            showMessage(
                "Your ATM session may expire soon.",
                "warning"
            );

        }

    }, 8 * 60 * 1000);

}


// ==========================================
// PREVENT DOUBLE FORM SUBMIT
// ==========================================

function initFormProtection() {

    const forms = document.querySelectorAll(
        "form"
    );


    forms.forEach(function (form) {

        let submitted = false;


        form.addEventListener(
            "submit",
            function (event) {

                if (
                    event.defaultPrevented
                ) {

                    return;

                }


                if (submitted) {

                    event.preventDefault();

                    return;

                }


                if (
                    !form.checkValidity()
                ) {

                    return;

                }


                submitted = true;


                const submitButton = form.querySelector(
                    'button[type="submit"], ' +
                    'input[type="submit"]'
                );


                if (!submitButton) {

                    return;

                }


                submitButton.disabled = true;


                if (
                    submitButton.tagName === "BUTTON"
                ) {

                    submitButton.dataset.oldText =
                        submitButton.innerText;

                    submitButton.innerText =
                        "Processing...";

                } else {

                    submitButton.dataset.oldValue =
                        submitButton.value;

                    submitButton.value =
                        "Processing...";

                }

            }
        );

    });

}


// ==========================================
// GLOBAL MESSAGE
// ==========================================

function showMessage(
    message,
    type = "info"
) {

    const oldMessage = document.querySelector(
        ".js-global-message"
    );


    if (oldMessage) {

        oldMessage.remove();

    }


    const messageBox = document.createElement(
        "div"
    );


    messageBox.className =
        "message js-global-message "
        + type;


    messageBox.innerText =
        message;


    messageBox.style.position =
        "fixed";

    messageBox.style.top =
        "20px";

    messageBox.style.right =
        "20px";

    messageBox.style.zIndex =
        "9999";

    messageBox.style.maxWidth =
        "350px";

    messageBox.style.boxShadow =
        "0 10px 30px rgba(0, 0, 0, 0.2)";


    document.body.appendChild(
        messageBox
    );


    setTimeout(function () {

        messageBox.style.transition =
            "0.4s";

        messageBox.style.opacity =
            "0";

        messageBox.style.transform =
            "translateY(-10px)";


        setTimeout(function () {

            messageBox.remove();

        }, 400);

    }, 4000);

}