`default_nettype none

module python_controller #(
    parameter int DATA_WIDTH = 8,
    parameter int FRAC_BITS = 0
) (
    input logic clk,
    input logic rst,
    input logic [7:0] sample,
    output logic [7:0] alarm
);

// _VAL_0_0 = 0.0 in fixed-point Q8.0
localparam logic [7:0] _VAL_0_0 = 8'd0;
// _VAL_1_0 = 1.0 in fixed-point Q8.4
localparam logic [11:0] _VAL_1_0 = 12'd16;
// _VAL_1_0_2 = 1.0 in fixed-point Q8.0
localparam logic [7:0] _VAL_1_0_2 = 8'd1;
// _VAL_2_0 = 2.0 in fixed-point Q8.0
localparam logic [7:0] _VAL_2_0 = 8'd2;
// _VAL_5_0 = 5.0 in fixed-point Q8.0
localparam logic [7:0] _VAL_5_0 = 8'd5;
function automatic logic [11:0] conv_logic_8_to_ufixed_12_4(
    input logic [7:0] value
);
    conv_logic_8_to_ufixed_12_4 = (value ? _VAL_1_0 : '0);
endfunction

function automatic logic [7:0] conv_logic_8_to_ufixed_8_0(
    input logic [7:0] value
);
    conv_logic_8_to_ufixed_8_0 = (value ? _VAL_1_0_2 : '0);
endfunction

function automatic logic [7:0] conv_ufixed_12_4_to_ufixed_8_0(
    input logic [11:0] value
);
    conv_ufixed_12_4_to_ufixed_8_0 = (value >>> 4);
endfunction

function automatic logic [7:0] conv_ufixed_8_0_to_logic_8(
    input logic [7:0] value
);
    conv_ufixed_8_0_to_logic_8 = value;
endfunction
logic [11:0] sensor0__level;
logic [7:0] sensor1__level;

logic [7:0] state_alarm;
logic [7:0] state_alarm_next;
logic [7:0] state_alarm_prod;
logic state_alarm_used;
logic [7:0] state_sample;
logic [7:0] state_sample_next;
logic [7:0] state_sample_prod;
logic state_sample_used;

python_sensor sensor0 (
    .clk(clk),
    .rst(rst),
    .raw(conv_logic_8_to_ufixed_12_4(sample)),
    .level(sensor0__level)
);

python_sensor_reset sensor1 (
    .clk(clk),
    .rst(rst),
    .raw(conv_logic_8_to_ufixed_8_0(sample)),
    .level(sensor1__level)
);

always_comb begin
    state_alarm_prod = '0;
    state_alarm_used = 1'b0;
    state_sample_prod = '0;
    state_sample_used = 1'b0;

    // (sensor0.level > 2) : sensor0.level -> alarm
    if ((conv_ufixed_12_4_to_ufixed_8_0(sensor0__level) > _VAL_2_0)) begin
        state_alarm_prod = state_alarm_prod + conv_ufixed_12_4_to_ufixed_8_0(sensor0__level);
    end
    // (sensor1.level > 5) : sensor1.level -> alarm
    if ((sensor1__level > _VAL_5_0)) begin
        state_alarm_prod = state_alarm_prod + sensor1__level;
    end
    // True : (alarm * 0) -> alarm
    if (1'b1) begin
        state_alarm_prod = state_alarm_prod + ((state_alarm * _VAL_0_0) >>> FRAC_BITS);
        state_alarm_used = 1'b1;
    end

    state_alarm_next = state_alarm;
    if (state_alarm_used) begin
        state_alarm_next = '0;
    end
    state_alarm_next = state_alarm_next + state_alarm_prod;
    state_sample_next = conv_logic_8_to_ufixed_8_0(sample);
    if (state_sample_used) begin
        state_sample_next = '0;
    end
    state_sample_next = state_sample_next + state_sample_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset alarm = 0.0
        state_alarm <= 8'd0;
        // reset sample = 0.0
        state_sample <= 8'd0;
    end else begin
        state_alarm <= state_alarm_next;
        state_sample <= state_sample_next;
    end
end

assign alarm = conv_ufixed_8_0_to_logic_8(state_alarm);

endmodule