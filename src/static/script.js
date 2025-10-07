var return_to_top = document.getElementById('return-to-top');

var lidarr_get_artists_button = document.getElementById(
	'lidarr-get-artists-button'
);
var start_stop_button = document.getElementById('start-stop-button');
var lidarr_status = document.getElementById('lidarr-status');
var lidarr_spinner = document.getElementById('lidarr-spinner');
var load_more_button = document.getElementById('load-more-btn');
var header_spinner = document.getElementById('artists-loading-spinner');

var lidarr_item_list = document.getElementById('lidarr-item-list');
var lidarr_select_all_checkbox = document.getElementById('lidarr-select-all');
var lidarr_select_all_container = document.getElementById(
	'lidarr-select-all-container'
);

var config_modal = document.getElementById('config-modal');
var lidarr_sidebar = document.getElementById('lidarr-sidebar');

var save_message = document.getElementById('save-message');
var save_changes_button = document.getElementById('save-changes-button');
const lidarr_address = document.getElementById('lidarr-address');
const lidarr_api_key = document.getElementById('lidarr-api-key');
const root_folder_path = document.getElementById('root-folder-path');
const youtube_api_key = document.getElementById('youtube-api-key');

var lidarr_items = [];
var socket = io();

// Initial load flow control
let initialLoadComplete = false;
let initialLoadHasMore = false;
let loadMorePending = false;

function show_header_spinner() {
	if (header_spinner) {
		header_spinner.classList.remove('d-none');
	}
}

function hide_header_spinner() {
	if (header_spinner) {
		header_spinner.classList.add('d-none');
	}
}

function escape_html(text) {
	if (text === null || text === undefined) {
		return '';
	}
	var div = document.createElement('div');
	div.textContent = text;
	return div.innerHTML;
}

function render_loading_spinner(message) {
	return `
        <div class="d-flex justify-content-center align-items-center py-4">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">${message}</span>
            </div>
        </div>
    `;
}

function show_modal_with_lock(modalId, onHidden) {
	var modalEl = document.getElementById(modalId);
	if (!modalEl) {
		return null;
	}
	var scrollbarWidth =
		window.innerWidth - document.documentElement.clientWidth;
	document.body.style.overflow = 'hidden';
	document.body.style.paddingRight = `${scrollbarWidth}px`;
	var modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
	var hiddenHandler = function () {
		document.body.style.overflow = 'auto';
		document.body.style.paddingRight = '0';
		modalEl.removeEventListener('hidden.bs.modal', hiddenHandler);
		if (typeof onHidden === 'function') {
			onHidden();
		}
	};
	modalEl.addEventListener('hidden.bs.modal', hiddenHandler, { once: true });
	modalInstance.show();
	return modalInstance;
}

function ensure_audio_modal_visible() {
	var modalEl = document.getElementById('audio-player-modal');
	if (!modalEl) {
		return;
	}
	if (!modalEl.classList.contains('show')) {
		show_modal_with_lock('audio-player-modal', function () {
			var container = document.getElementById('audio-player-modal-body');
			if (container) {
				container.innerHTML = '';
			}
		});
	}
}

function show_audio_modal_loading(artistName) {
	var bodyEl = document.getElementById('audio-player-modal-body');
	var titleEl = document.getElementById('audio-player-modal-label');
	if (titleEl) {
		titleEl.textContent = `Fetching sample for ${artistName}`;
	}
	if (bodyEl) {
		bodyEl.innerHTML = render_loading_spinner('Loading sample...');
	}
	ensure_audio_modal_visible();
}

function update_audio_modal_content(artist, track, videoId) {
	var bodyEl = document.getElementById('audio-player-modal-body');
	var titleEl = document.getElementById('audio-player-modal-label');
	var safeArtist = escape_html(artist);
	var safeTrack = escape_html(track);
	var safeVideoId = encodeURIComponent(videoId);
	if (titleEl) {
		titleEl.textContent = `${artist} – ${track}`;
	}
	if (bodyEl) {
		bodyEl.innerHTML = `
            <div class="ratio ratio-16x9">
                <iframe src="https://www.youtube.com/embed/${safeVideoId}?autoplay=1" title="${safeArtist} – ${safeTrack}"
                    allow="autoplay; encrypted-media" allowfullscreen></iframe>
            </div>
        `;
	}
	ensure_audio_modal_visible();
}

function show_audio_modal_error(message) {
	var bodyEl = document.getElementById('audio-player-modal-body');
	var titleEl = document.getElementById('audio-player-modal-label');
	if (titleEl) {
		titleEl.textContent = 'Sample unavailable';
	}
	if (bodyEl) {
		var safeMessage = escape_html(message);
		bodyEl.innerHTML = `<div class="alert alert-warning mb-0">${safeMessage}</div>`;
	}
	ensure_audio_modal_visible();
}

function show_bio_modal_loading(artistName) {
	var titleEl = document.getElementById('bio-modal-title');
	var bodyEl = document.getElementById('modal-body');
	if (titleEl) {
		titleEl.textContent = artistName;
	}
	if (bodyEl) {
		bodyEl.innerHTML = render_loading_spinner('Loading biography...');
	}
	show_modal_with_lock('bio-modal-modal');
}

function check_if_all_selected() {
	var checkboxes = document.querySelectorAll('input[name="lidarr-item"]');
	var all_checked = true;
	for (var i = 0; i < checkboxes.length; i++) {
		if (!checkboxes[i].checked) {
			all_checked = false;
			break;
		}
	}
	lidarr_select_all_checkbox.checked = all_checked;
}

function load_lidarr_data(response) {
	var every_check_box = document.querySelectorAll(
		'input[name="lidarr-item"]'
	);
	if (response.Running) {
		start_stop_button.classList.remove('btn-success');
		start_stop_button.classList.add('btn-warning');
		start_stop_button.textContent = 'Stop';
		every_check_box.forEach((item) => {
			item.disabled = true;
		});
		lidarr_select_all_checkbox.disabled = true;
		lidarr_get_artists_button.disabled = true;
	} else {
		start_stop_button.classList.add('btn-success');
		start_stop_button.classList.remove('btn-warning');
		start_stop_button.textContent = 'Start';
		every_check_box.forEach((item) => {
			item.disabled = false;
		});
		lidarr_select_all_checkbox.disabled = false;
		lidarr_get_artists_button.disabled = false;
	}
	check_if_all_selected();
}

function create_load_more_button() {
	if (!load_more_button) return;
	if (!initialLoadComplete || !initialLoadHasMore) {
		load_more_button.classList.add('d-none');
		load_more_button.disabled = false;
		return;
	}
	load_more_button.classList.remove('d-none');
	load_more_button.disabled = loadMorePending;
}

function remove_load_more_button() {
	if (!load_more_button) return;
	load_more_button.classList.add('d-none');
	load_more_button.disabled = false;
}

function append_artists(artists) {
	var artist_row = document.getElementById('artist-row');
	var template = document.getElementById('artist-template');
	if (!initialLoadComplete) {
		remove_load_more_button();
	}
	artists.forEach(function (artist) {
		var clone = document.importNode(template.content, true);
		var artist_col = clone.querySelector('#artist-column');

		artist_col.querySelector('.card-title').textContent = artist.Name;
		var similarityEl = artist_col.querySelector('.similarity');
		if (similarityEl) {
			const hasScore =
				typeof artist.SimilarityScore === 'number' &&
				!Number.isNaN(artist.SimilarityScore);
			if (
				hasScore ||
				(typeof artist.Similarity === 'string' &&
					artist.Similarity.trim().length > 0)
			) {
				const label =
					typeof artist.Similarity === 'string' &&
					artist.Similarity.trim().length > 0
						? artist.Similarity
						: `Similarity: ${(artist.SimilarityScore * 100).toFixed(
								1
						  )}%`;
				similarityEl.textContent = label;
				similarityEl.classList.remove('d-none');
			} else {
				similarityEl.textContent = '';
				similarityEl.classList.add('d-none');
			}
		}
		artist_col.querySelector('.genre').textContent = artist.Genre;
		if (artist.Img_Link) {
			artist_col.querySelector('.card-img-top').src = artist.Img_Link;
			artist_col.querySelector('.card-img-top').alt = artist.Name;
		} else {
			artist_col
				.querySelector('.artist-img-container')
				.removeChild(artist_col.querySelector('.card-img-top'));
		}
		var add_button = artist_col.querySelector('.add-to-lidarr-btn');
		add_button.dataset.defaultText =
			add_button.dataset.defaultText || add_button.textContent;
		add_button.addEventListener('click', function () {
			add_to_lidarr(artist.Name, add_button);
		});
		artist_col
			.querySelector('.get-preview-btn')
			.addEventListener('click', function () {
				preview_req(artist.Name);
			});
		// Listen to Sample button logic
		artist_col
			.querySelector('.listen-sample-btn')
			.addEventListener('click', function () {
				listenSampleReq(artist.Name);
			});
		artist_col.querySelector('.followers').textContent = artist.Followers;
		artist_col.querySelector('.popularity').textContent = artist.Popularity;

		if (
			artist.Status === 'Added' ||
			artist.Status === 'Already in Lidarr'
		) {
			artist_col
				.querySelector('.card-body')
				.classList.add('status-green');
			add_button.classList.remove('btn-primary');
			add_button.classList.add('btn-secondary');
			add_button.disabled = true;
			add_button.textContent = artist.Status;
		} else if (
			artist.Status === 'Failed to Add' ||
			artist.Status === 'Invalid Path'
		) {
			artist_col.querySelector('.card-body').classList.add('status-red');
			add_button.classList.remove('btn-primary');
			add_button.classList.add('btn-danger');
			add_button.disabled = true;
			add_button.textContent = artist.Status;
		} else {
			artist_col.querySelector('.card-body').classList.add('status-blue');
		}
		artist_row.appendChild(clone);
	});
	if (initialLoadComplete) {
		create_load_more_button();
	}
}

// Remove infinite scroll triggers
window.removeEventListener('scroll', function () {});
window.removeEventListener('touchmove', function () {});
window.removeEventListener('touchend', function () {});

function add_to_lidarr(artist_name, buttonEl) {
	if (socket.connected) {
		if (buttonEl) {
			buttonEl.disabled = true;
			buttonEl.innerHTML =
				'<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Adding...';
			buttonEl.classList.remove('btn-primary', 'btn-danger');
			if (!buttonEl.classList.contains('btn-secondary')) {
				buttonEl.classList.add('btn-secondary');
			}
			buttonEl.dataset.loading = 'true';
		}
		socket.emit('adder', encodeURIComponent(artist_name));
	} else {
		show_toast('Connection Lost', 'Please reload to continue.');
	}
}

function show_toast(header, message) {
	var toast_container = document.querySelector('.toast-container');
	var toast_template = document
		.getElementById('toast-template')
		.cloneNode(true);
	toast_template.classList.remove('d-none');

	toast_template.querySelector('.toast-header strong').textContent = header;
	toast_template.querySelector('.toast-body').textContent = message;
	toast_template.querySelector('.text-muted').textContent =
		new Date().toLocaleString();

	toast_container.appendChild(toast_template);

	var toast = new bootstrap.Toast(toast_template);
	toast.show();

	toast_template.addEventListener('hidden.bs.toast', function () {
		toast_template.remove();
	});
}

return_to_top.addEventListener('click', function () {
	window.scrollTo({ top: 0, behavior: 'smooth' });
});

lidarr_select_all_checkbox.addEventListener('change', function () {
	var is_checked = this.checked;
	var checkboxes = document.querySelectorAll('input[name="lidarr-item"]');
	checkboxes.forEach(function (checkbox) {
		checkbox.checked = is_checked;
	});
});

lidarr_get_artists_button.addEventListener('click', function () {
	lidarr_get_artists_button.disabled = true;
	lidarr_spinner.classList.remove('d-none');
	lidarr_status.textContent = 'Accessing Lidarr API';
	lidarr_item_list.innerHTML = '';
	socket.emit('get_lidarr_artists');
});

start_stop_button.addEventListener('click', function () {
	var running_state =
		start_stop_button.textContent.trim() === 'Start' ? true : false;
	if (running_state) {
		// Reset initial load state and show overlay until first results arrive
		initialLoadComplete = false;
		initialLoadHasMore = false;
		loadMorePending = false;
		show_header_spinner();
		remove_load_more_button();

		start_stop_button.classList.remove('btn-success');
		start_stop_button.classList.add('btn-warning');
		start_stop_button.textContent = 'Stop';
		var checked_items = Array.from(
			document.querySelectorAll('input[name="lidarr-item"]:checked')
		).map((item) => item.value);
		document
			.querySelectorAll('input[name="lidarr-item"]')
			.forEach((item) => {
				item.disabled = true;
			});
		lidarr_get_artists_button.disabled = true;
		lidarr_select_all_checkbox.disabled = true;
		socket.emit('start_req', checked_items);
	} else {
		hide_header_spinner();

		start_stop_button.classList.add('btn-success');
		start_stop_button.classList.remove('btn-warning');
		start_stop_button.textContent = 'Start';
		document
			.querySelectorAll('input[name="lidarr-item"]')
			.forEach((item) => {
				item.disabled = false;
			});
		lidarr_get_artists_button.disabled = false;
		lidarr_select_all_checkbox.disabled = false;
		socket.emit('stop_req');
	}
});

if (load_more_button) {
	load_more_button.addEventListener('click', function () {
		if (loadMorePending || load_more_button.disabled) {
			return;
		}
		loadMorePending = true;
		load_more_button.disabled = true;
		show_header_spinner();
		socket.emit('load_more_artists');
	});
}

if (save_changes_button && config_modal) {
	save_changes_button.addEventListener('click', () => {
		socket.emit('update_settings', {
			lidarr_address: lidarr_address.value,
			lidarr_api_key: lidarr_api_key.value,
			root_folder_path: root_folder_path.value,
			youtube_api_key: youtube_api_key.value,
		});
		if (save_message) {
			save_message.style.display = 'block';
			setTimeout(function () {
				save_message.style.display = 'none';
			}, 1000);
		}
	});

	config_modal.addEventListener('show.bs.modal', function () {
		socket.emit('load_settings');

		function handle_settings_loaded(settings) {
			lidarr_address.value = settings.lidarr_address;
			lidarr_api_key.value = settings.lidarr_api_key;
			root_folder_path.value = settings.root_folder_path;
			youtube_api_key.value = settings.youtube_api_key;
			socket.off('settingsLoaded', handle_settings_loaded);
		}
		socket.on('settingsLoaded', handle_settings_loaded);
	});
}

lidarr_sidebar.addEventListener('show.bs.offcanvas', function (event) {
	socket.emit('side_bar_opened');
});

socket.on('lidarr_sidebar_update', (response) => {
	if (response.Status == 'Success') {
		lidarr_status.textContent = 'Lidarr List Retrieved';
		lidarr_items = response.Data;
		lidarr_item_list.innerHTML = '';
		lidarr_select_all_container.classList.remove('d-none');

		for (var i = 0; i < lidarr_items.length; i++) {
			var item = lidarr_items[i];

			var div = document.createElement('div');
			div.className = 'form-check';

			var input = document.createElement('input');
			input.type = 'checkbox';
			input.className = 'form-check-input';
			input.id = 'lidarr-' + i;
			input.name = 'lidarr-item';
			input.value = item.name;

			if (item.checked) {
				input.checked = true;
			}

			var label = document.createElement('label');
			label.className = 'form-check-label';
			label.htmlFor = 'lidarr-' + i;
			label.textContent = item.name;

			input.addEventListener('change', function () {
				check_if_all_selected();
			});

			div.appendChild(input);
			div.appendChild(label);

			lidarr_item_list.appendChild(div);
		}
	} else {
		lidarr_status.textContent = response.Code;
	}
	lidarr_get_artists_button.disabled = false;
	lidarr_spinner.classList.add('d-none');
	load_lidarr_data(response);
	if (!response.Running) {
		hide_header_spinner();
	}
});

socket.on('refresh_artist', (artist) => {
	var artist_cards = document.querySelectorAll('#artist-column');
	artist_cards.forEach(function (card) {
		var card_body = card.querySelector('.card-body');
		var card_artist_name = card_body
			.querySelector('.card-title')
			.textContent.trim();

		if (card_artist_name === artist.Name) {
			card_body.classList.remove(
				'status-green',
				'status-red',
				'status-blue'
			);

			var add_button = card_body.querySelector('.add-to-lidarr-btn');

			if (
				artist.Status === 'Added' ||
				artist.Status === 'Already in Lidarr'
			) {
				card_body.classList.add('status-green');
				add_button.classList.remove('btn-primary');
				add_button.classList.add('btn-secondary');
				add_button.disabled = true;
				add_button.innerHTML = artist.Status;
				add_button.dataset.loading = '';
			} else if (
				artist.Status === 'Failed to Add' ||
				artist.Status === 'Invalid Path'
			) {
				card_body.classList.add('status-red');
				add_button.classList.remove('btn-primary');
				add_button.classList.add('btn-danger');
				add_button.disabled = true;
				add_button.innerHTML = artist.Status;
				add_button.dataset.loading = '';
			} else {
				card_body.classList.add('status-blue');
				add_button.disabled = false;
				add_button.classList.remove('btn-danger', 'btn-secondary');
				if (!add_button.classList.contains('btn-primary')) {
					add_button.classList.add('btn-primary');
				}
				add_button.innerHTML =
					add_button.dataset.defaultText || 'Add to Lidarr';
				add_button.dataset.loading = '';
			}
			return;
		}
	});
});

socket.on('more_artists_loaded', function (data) {
	append_artists(data);
});

// Server signals that initial batches are complete: show the Load More button now
socket.on('initial_load_complete', function (payload) {
	initialLoadComplete = true;
	initialLoadHasMore = !!(payload && payload.hasMore);
	loadMorePending = false;
	hide_header_spinner();
	if (initialLoadHasMore) {
		create_load_more_button();
	} else {
		remove_load_more_button();
	}
});

socket.on('load_more_complete', function (payload) {
	loadMorePending = false;
	initialLoadHasMore = !!(payload && payload.hasMore);
	hide_header_spinner();
	if (initialLoadHasMore) {
		create_load_more_button();
	} else {
		remove_load_more_button();
	}
});

socket.on('clear', function () {
	clear_all();
});

socket.on('new_toast_msg', function (data) {
	show_toast(data.title, data.message);
});

socket.on('disconnect', function () {
	show_toast('Connection Lost', 'Please reconnect to continue.');
	hide_header_spinner();
	clear_all();
});

function clear_all() {
	var artist_row = document.getElementById('artist-row');
	var artist_cards = artist_row.querySelectorAll('#artist-column');
	artist_cards.forEach(function (card) {
		card.remove();
	});
	remove_load_more_button();
	initialLoadComplete = false;
	initialLoadHasMore = false;
	loadMorePending = false;
	// spinner state is controlled by the caller
}

var preview_request_flag = false;

function preview_req(artist_name) {
	if (!preview_request_flag) {
		preview_request_flag = true;
		show_bio_modal_loading(artist_name);
		socket.emit('preview_req', encodeURIComponent(artist_name));
		setTimeout(() => {
			preview_request_flag = false;
		}, 1500);
	}
}

socket.on('lastfm_preview', function (preview_info) {
	var modal_body = document.getElementById('modal-body');
	var modal_title = document.getElementById('bio-modal-title');
	var modalEl = document.getElementById('bio-modal-modal');

	if (typeof preview_info === 'string') {
		if (modal_body) {
			var safeMessage = escape_html(preview_info);
			modal_body.innerHTML = `<div class="alert alert-warning mb-0">${safeMessage}</div>`;
		}
		show_toast('Error Retrieving Bio', preview_info);
		if (modalEl && !modalEl.classList.contains('show')) {
			show_modal_with_lock('bio-modal-modal');
		}
		return;
	}

	var artist_name = preview_info.artist_name;
	var biography = preview_info.biography;
	if (modal_title) {
		modal_title.textContent = artist_name;
	}
	if (modal_body) {
		modal_body.innerHTML = DOMPurify.sanitize(biography);
	}
	if (modalEl && !modalEl.classList.contains('show')) {
		show_modal_with_lock('bio-modal-modal');
	}
});

const theme_switch = document.getElementById('theme-switch');
if (theme_switch) {
	const saved_theme = localStorage.getItem('theme');
	const saved_switch_position = localStorage.getItem('switch-position');

	if (saved_switch_position) {
		theme_switch.checked = saved_switch_position === 'true';
	}

	if (saved_theme) {
		document.documentElement.setAttribute('data-bs-theme', saved_theme);
	}

	theme_switch.addEventListener('click', () => {
		if (document.documentElement.getAttribute('data-bs-theme') === 'dark') {
			document.documentElement.setAttribute('data-bs-theme', 'light');
		} else {
			document.documentElement.setAttribute('data-bs-theme', 'dark');
		}
		localStorage.setItem(
			'theme',
			document.documentElement.getAttribute('data-bs-theme')
		);
		localStorage.setItem('switch_position', theme_switch.checked);
	});
}

// Listen Sample button event
function listenSampleReq(artist_name) {
	show_audio_modal_loading(artist_name);
	socket.emit('prehear_req', encodeURIComponent(artist_name));
}

socket.on('prehear_result', function (data) {
	if (data.videoId) {
		update_audio_modal_content(data.artist, data.track, data.videoId);
	} else {
		var message = data.error || 'No YouTube video found for this artist.';
		show_audio_modal_error(message);
		show_toast('No sample found', message);
	}
});
