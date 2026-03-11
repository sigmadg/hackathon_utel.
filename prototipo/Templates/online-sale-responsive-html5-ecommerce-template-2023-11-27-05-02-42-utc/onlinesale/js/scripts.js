

jQuery(function($) {
	
	
	

	

	/*
	| ----------------------------------------------------------------------------------
	| Range slider
	| ----------------------------------------------------------------------------------
	*/
	$('.range-slider').each(function() {
		var $this = $(this),
			configs = new Array();
		
		configs['min'] = ( $this.data('min') === undefined ) ? 0 : $this.data('min');
		configs['max'] = ( $this.data('max') === undefined ) ? 100 : $this.data('max');
		configs['start'] = ( $this.data('start') === undefined ) ? [20, 80] : $this.data('start');
		configs['step'] = ( $this.data('step') === undefined ) ? 1 : $this.data('step');
		
		var percentage = {
			to : function (range, value) {
				value = range[0] < 0 ? value + Math.abs(range[0]) : value - range[0];
				return (value * 100) / this._length(range);
			},
			_length : function (range) {
				return (range[0] > range[1] ? range[0] - range[1] : range[1] - range[0]);
			}
		}
		
		$this.noUiSlider({
			range: [configs['min'], configs['max']],
			start: configs['start'],
			step: configs['step'],
			slide: function() {
				var values = $(this).val(),
					range = $this.data('setup').settings.range;
					
				$this.siblings('.range-slider-value').find('> .min').text( '$' + values[0] ).css({ 'left': percentage.to(range, values[0]) + '%', 'visibility': 'visible', 'margin-left': (-0.6) * $this.siblings('.range-slider-value').find('> .min').outerWidth() });
				$this.siblings('.range-slider-value').find('> .max').text( '$' + values[1] ).css({ 'left': percentage.to(range, values[1]) + '%', 'visibility': 'visible', 'margin-left': (-0.6) * $this.siblings('.range-slider-value').find('> .max').outerWidth() });
			}
		});
		
		var settings = $this.data('setup').settings;
		$this.siblings('.range-slider-value').find('> .min').text( '$' + settings.start[0] ).css({ 'left': percentage.to(settings.range, settings.start[0]) + '%', 'visibility': 'visible', 'margin-left': (-0.6) * $this.siblings('.range-slider-value').find('> .min').outerWidth() });
		$this.siblings('.range-slider-value').find('> .max').text( '$' + settings.start[1] ).css({ 'left': percentage.to(settings.range, settings.start[1]) + '%', 'visibility': 'visible', 'margin-left': (-0.6) * $this.siblings('.range-slider-value').find('> .max').outerWidth() });
	});
	

	

});