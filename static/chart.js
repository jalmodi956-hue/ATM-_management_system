document.addEventListener("DOMContentLoaded", function () {
    initATMCharts();
});


// ==========================================
// ATM CHART INITIALIZATION
// ==========================================

function initATMCharts() {

    if (typeof Chart === "undefined") {
        console.warn("Chart.js library is not loaded.");
        return;
    }

    initTransactionChart();
    initTransactionPieChart();
}


// ==========================================
// GET NUMBER FROM DATA ATTRIBUTE
// ==========================================

function getChartNumber(element, name) {

    if (!element) {
        return 0;
    }

    const value = Number(
        element.dataset[name]
    );

    if (
        Number.isNaN(value)
        || value < 0
    ) {
        return 0;
    }

    return value;
}


// ==========================================
// TRANSACTION BAR CHART
// ==========================================

function initTransactionChart() {

    const canvas = document.getElementById(
        "transactionChart"
    );

    if (!canvas) {
        return;
    }

    const deposit = getChartNumber(
        canvas,
        "deposit"
    );

    const withdraw = getChartNumber(
        canvas,
        "withdraw"
    );

    const transfer = getChartNumber(
        canvas,
        "transfer"
    );

    const fixedDeposit = getChartNumber(
        canvas,
        "fixedDeposit"
    );


    new Chart(
        canvas.getContext("2d"),
        {
            type: "bar",

            data: {
                labels: [
                    "Deposit",
                    "Withdrawal",
                    "Transfer",
                    "Fixed Deposit"
                ],

                datasets: [
                    {
                        label: "Transaction Amount (₹)",

                        data: [
                            deposit,
                            withdraw,
                            transfer,
                            fixedDeposit
                        ],

                        backgroundColor: [
                            "rgba(22, 163, 74, 0.75)",
                            "rgba(220, 38, 38, 0.75)",
                            "rgba(37, 99, 235, 0.75)",
                            "rgba(147, 51, 234, 0.75)"
                        ],

                        borderColor: [
                            "rgb(22, 163, 74)",
                            "rgb(220, 38, 38)",
                            "rgb(37, 99, 235)",
                            "rgb(147, 51, 234)"
                        ],

                        borderWidth: 1,

                        borderRadius: 8
                    }
                ]
            },

            options: {
                responsive: true,

                maintainAspectRatio: false,

                animation: {
                    duration: 1000
                },

                plugins: {
                    legend: {
                        display: true
                    },

                    tooltip: {
                        callbacks: {
                            label: function (context) {

                                return (
                                    " ₹"
                                    + Number(
                                        context.raw
                                    ).toLocaleString(
                                        "en-IN",
                                        {
                                            minimumFractionDigits: 2,
                                            maximumFractionDigits: 2
                                        }
                                    )
                                );
                            }
                        }
                    }
                },

                scales: {
                    y: {
                        beginAtZero: true,

                        ticks: {
                            callback: function (value) {

                                return (
                                    "₹"
                                    + Number(
                                        value
                                    ).toLocaleString(
                                        "en-IN"
                                    )
                                );
                            }
                        }
                    }
                }
            }
        }
    );
}


// ==========================================
// TRANSACTION PIE CHART
// ==========================================

function initTransactionPieChart() {

    const canvas = document.getElementById(
        "transactionPieChart"
    );

    if (!canvas) {
        return;
    }

    const deposit = getChartNumber(
        canvas,
        "deposit"
    );

    const withdraw = getChartNumber(
        canvas,
        "withdraw"
    );

    const transfer = getChartNumber(
        canvas,
        "transfer"
    );

    const fixedDeposit = getChartNumber(
        canvas,
        "fixedDeposit"
    );


    const values = [
        deposit,
        withdraw,
        transfer,
        fixedDeposit
    ];


    const hasData = values.some(
        function (value) {
            return value > 0;
        }
    );


    if (!hasData) {

        const parent = canvas.parentElement;

        if (parent) {

            const message = document.createElement(
                "p"
            );

            message.innerText =
                "No transaction data available.";

            message.style.textAlign =
                "center";

            message.style.padding =
                "20px";

            parent.appendChild(
                message
            );
        }

        canvas.style.display = "none";

        return;
    }


    new Chart(
        canvas.getContext("2d"),
        {
            type: "doughnut",

            data: {
                labels: [
                    "Deposit",
                    "Withdrawal",
                    "Transfer",
                    "Fixed Deposit"
                ],

                datasets: [
                    {
                        data: values,

                        backgroundColor: [
                            "rgba(22, 163, 74, 0.80)",
                            "rgba(220, 38, 38, 0.80)",
                            "rgba(37, 99, 235, 0.80)",
                            "rgba(147, 51, 234, 0.80)"
                        ],

                        borderWidth: 2
                    }
                ]
            },

            options: {
                responsive: true,

                maintainAspectRatio: false,

                cutout: "60%",

                animation: {
                    duration: 1000
                },

                plugins: {
                    legend: {
                        position: "bottom"
                    },

                    tooltip: {
                        callbacks: {
                            label: function (context) {

                                const value = Number(
                                    context.raw
                                );

                                return (
                                    " "
                                    + context.label
                                    + ": ₹"
                                    + value.toLocaleString(
                                        "en-IN",
                                        {
                                            minimumFractionDigits: 2,
                                            maximumFractionDigits: 2
                                        }
                                    )
                                );
                            }
                        }
                    }
                }
            }
        }
    );
}