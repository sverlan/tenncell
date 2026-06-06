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

// _VAL_1_0 = 1.0 in fixed-point Q30.10
localparam logic [39:0] _VAL_1_0 = 40'd1024;
// _VAL_48_0 = 48.0 in fixed-point Q30.10
localparam logic [39:0] _VAL_48_0 = 40'd49152;
// _VAL_49_0 = 49.0 in fixed-point Q30.10
localparam logic [39:0] _VAL_49_0 = 40'd50176;
function automatic logic [39:0] conv_logic_to_ufixed_40_10(
    input logic value
);
    conv_logic_to_ufixed_40_10 = (value ? _VAL_1_0 : '0);
endfunction

function automatic logic conv_ufixed_40_10_to_logic(
    input logic [39:0] value
);
    conv_ufixed_40_10_to_logic = (value != '0);
endfunction

function automatic logic [7:0] conv_ufixed_40_10_to_uint_8(
    input logic [39:0] value
);
    conv_ufixed_40_10_to_uint_8 = ((value >= '0) ? (value >>> 10) : -((-value) >>> 10));
endfunction
logic [39:0] state_led_state;
logic [39:0] state_led_state_next;
logic [39:0] state_led_state_prod;
logic [39:0] state_trigger;
logic [39:0] state_trigger_next;
logic [39:0] state_trigger_prod;
logic [39:0] state_tx_data;
logic [39:0] state_tx_data_next;
logic [39:0] state_tx_data_prod;
logic [39:0] state_tx_valid;
logic [39:0] state_tx_valid_next;
logic [39:0] state_tx_valid_prod;
logic [39:0] state_uart_ready;
logic [39:0] state_uart_ready_next;
logic [39:0] state_uart_ready_prod;

always_comb begin
    state_led_state_prod = '0;
    state_trigger_prod = '0;
    state_tx_data_prod = '0;
    state_tx_valid_prod = '0;
    state_uart_ready_prod = '0;

    // (((trigger > 0) && (uart_ready > 0)) && (led_state == 0)) : 48 -> tx_data
    if ((((state_trigger > 1'b0) && (state_uart_ready > 1'b0)) && (state_led_state == 1'b0))) begin
        state_tx_data_prod = state_tx_data_prod + _VAL_48_0;
    end
    // (((trigger > 0) && (uart_ready > 0)) && (led_state > 0)) : 49 -> tx_data
    if ((((state_trigger > 1'b0) && (state_uart_ready > 1'b0)) && (state_led_state > 1'b0))) begin
        state_tx_data_prod = state_tx_data_prod + _VAL_49_0;
    end
    // ((trigger > 0) && (uart_ready > 0)) : 1 -> tx_valid
    if (((state_trigger > 1'b0) && (state_uart_ready > 1'b0))) begin
        state_tx_valid_prod = state_tx_valid_prod + _VAL_1_0;
    end

    state_led_state_next = conv_logic_to_ufixed_40_10(led_state);
    state_led_state_next = state_led_state_next + state_led_state_prod;
    state_trigger_next = conv_logic_to_ufixed_40_10(trigger);
    state_trigger_next = state_trigger_next + state_trigger_prod;
    state_tx_data_next = '0;
    state_tx_data_next = state_tx_data_next + state_tx_data_prod;
    state_tx_valid_next = '0;
    state_tx_valid_next = state_tx_valid_next + state_tx_valid_prod;
    state_uart_ready_next = conv_logic_to_ufixed_40_10(uart_ready);
    state_uart_ready_next = state_uart_ready_next + state_uart_ready_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset led_state = 0.0
        state_led_state <= 40'd0;
        // reset trigger = 0.0
        state_trigger <= 40'd0;
        // reset tx_data = 0.0
        state_tx_data <= 40'd0;
        // reset tx_valid = 0.0
        state_tx_valid <= 40'd0;
        // reset uart_ready = 0.0
        state_uart_ready <= 40'd0;
    end else begin
        state_led_state <= state_led_state_next;
        state_trigger <= state_trigger_next;
        state_tx_data <= state_tx_data_next;
        state_tx_valid <= state_tx_valid_next;
        state_uart_ready <= state_uart_ready_next;
    end
end

assign tx_data = conv_ufixed_40_10_to_uint_8(state_tx_data);
assign tx_valid = conv_ufixed_40_10_to_logic(state_tx_valid);

endmodule