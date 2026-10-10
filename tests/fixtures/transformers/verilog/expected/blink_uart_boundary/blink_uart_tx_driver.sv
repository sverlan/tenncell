`default_nettype none

module blink_uart_tx_driver #(
    parameter int DATA_WIDTH = 40,
    parameter int FRAC_BITS = 10
) (
    input logic clk,
    input logic rst,
    input logic trigger,
    input logic led_state,
    input logic uart_ready,
    output logic [7:0] tx_data,
    output logic tx_valid
);

// LED_OFF_BYTE = 48.0 in fixed-point Q30.10
localparam logic [39:0] LED_OFF_BYTE = 40'd49152;
// LED_ON_BYTE = 49.0 in fixed-point Q30.10
localparam logic [39:0] LED_ON_BYTE = 40'd50176;

logic [7:0] state_tx_data;
logic [7:0] state_tx_data_next;
logic [7:0] state_tx_data_prod;
logic state_tx_valid;
logic state_tx_valid_next;
logic state_tx_valid_prod;

always_comb begin
    state_tx_data_prod = '0;
    state_tx_valid_prod = '0;

    // (((trigger > 0) && (uart_ready > 0)) && (led_state == 0)) : 48 -> tx_data
    if ((((trigger > 1'b0) && (uart_ready > 1'b0)) && (led_state == 1'b0))) begin
        state_tx_data_prod = state_tx_data_prod + 8'd48;
    end
    // (((trigger > 0) && (uart_ready > 0)) && (led_state > 0)) : 49 -> tx_data
    if ((((trigger > 1'b0) && (uart_ready > 1'b0)) && (led_state > 1'b0))) begin
        state_tx_data_prod = state_tx_data_prod + 8'd49;
    end
    // ((trigger > 0) && (uart_ready > 0)) : 1 -> tx_valid
    if (((trigger > 1'b0) && (uart_ready > 1'b0))) begin
        state_tx_valid_prod = state_tx_valid_prod + 1'b1;
    end

    state_tx_data_next = '0;
    state_tx_data_next = state_tx_data_next + state_tx_data_prod;
    state_tx_valid_next = '0;
    state_tx_valid_next = state_tx_valid_next + state_tx_valid_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset tx_data = 0.0
        state_tx_data <= 8'd0;
        // reset tx_valid = 0.0
        state_tx_valid <= 1'b0;
    end else begin
        state_tx_data <= state_tx_data_next;
        state_tx_valid <= state_tx_valid_next;
    end
end

assign tx_data = state_tx_data;
assign tx_valid = state_tx_valid;

endmodule
