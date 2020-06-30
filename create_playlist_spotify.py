#!/bin/python

import base64
import calendar
from datetime import date
import json
import requests
import webbrowser
import yaml

with open('secrets.yml', 'r') as stream:
    secrets = yaml.safe_load(stream)

# spotify
client_id = secrets['spotify_client_id']
client_secret = secrets['spotify_client_secret']
client_credentials = f'{client_id}:{client_secret}'
client_credentials_b64 = base64.b64encode(client_credentials.encode())
webbrowser.open(f'https://accounts.spotify.com/authorize?client_id={client_id}&response_type=code&redirect_uri=https%3A%2F%2Fexample.com%2Fcallback&scope=playlist-modify-public')
auth_code = input('''Sign in to Spotify and approve of the app's access then 
after the redirect to example.com copy and paste the <code> from the uri 
that opens in the browser into the terminal. 
It will look like https://example.com...code=<code> ''')
redirect_uri = 'https://example.com/callback' # Same as in spotify dev dashboard
token_url = 'https://accounts.spotify.com/api/token'
token_data = {
    'grant_type': 'authorization_code',
    'code': auth_code,
    'redirect_uri': redirect_uri
}
token_header = {
    'Authorization': f'Basic {client_credentials_b64.decode()}'
}
client_token_data = {
    'grant_type': 'client_credentials'
}
client_token_header = {
    'Authorization': f'Basic {client_credentials_b64.decode()}'
}

# lastfm
lfm_api_root = 'https://ws.audioscrobbler.com/2.0/'
lfm_api_key = secrets['last_fm_api_key']
user = secrets['last_fm_user']
# opts: 1month | 3month | 6month | 12month | overall
period = '3month'
limit = 50 # Results displayed per page
page = 1
lfm_payload = {
    'method': 'user.gettoptracks',
    'user': user,
    'limit': limit,
    'period': period,
    'api_key': lfm_api_key,
    'page': page,
    'format': 'json'
    }
pages = int(requests.get(url=lfm_api_root, params=lfm_payload).json()['toptracks']['@attr']['totalPages'])
artist_song = {}
track_play_rank_lim = 20 # Max no. of tracks to be included in lastfm playlist
top_tracks = requests.get(url=lfm_api_root, params=lfm_payload).json()['toptracks']['track']


def lfm_get_top_tracks(lfm_api_root, lfm_payload, pages, track_play_rank_lim):
    page = 1
    track_play_rank = 1
    # Flick through pages
    while page <= pages and track_play_rank <= track_play_rank_lim:
        track_num_on_page = 0
        lfm_payload.update({'page': page})
        top_tracks = requests.get(url=lfm_api_root, params=lfm_payload).json()['toptracks']['track']
        num_tracks_on_page = len(top_tracks)

        # Add each track on page to artist_song dict
        while track_num_on_page <= num_tracks_on_page - 1 and track_play_rank <= track_play_rank_lim:
            for tracks in top_tracks:
                artist_song.update({track_play_rank: {
                    'artist': top_tracks[track_num_on_page]['artist']['name'],
                    'song': top_tracks[track_num_on_page]['name']
                }})
                track_num_on_page += 1
                track_play_rank += 1
                if track_play_rank >= track_play_rank_lim:
                    break
        
        page += 1
    return artist_song

def generate_playlist_name(period, date):
    period_to_delta = {
        '1month': -1,
        '3month': -3,
        '6month': -6,
        '12month': -12,
        'overall': 'from the beginning'
    }
    delta = period_to_delta[period]
    if period == 'overall':
        return f'{delta}: top tracks'
    else:
        m, y = (date.month+delta) % 12, date.year + ((date.month)+delta-1) // 12
        if not m: m = 12
        d = min(date.day, calendar.monthrange(y, m)[1])
        start_date = date.replace(day=d,month=m, year=y)
        return f'{start_date} - {date}: top tracks'

# For requesting non-user specific data
def get_spotify_client_access_token():
    r = requests.post(token_url, data=client_token_data, headers=client_token_header)
    r_client_acces_token_data = r.json()
    client_access_token = r_client_acces_token_data['access_token']
    return client_access_token

def get_spotify_track_uris_from(artist_song_dict):
    sptfy_query_endpoint = 'https://api.spotify.com/v1/search'
    sptfy_query_header = {
    'Authorization': f'Bearer {get_spotify_client_access_token()}'
    }
    track_uri_list = []
    for position in artist_song_dict:
        artist = artist_song_dict[position]['artist']
        track = artist_song_dict[position]['song']
        search_string = f'{artist}+{track}'
        # Example: https://api.spotify.com/v1/search?q=tania%20bowra&type=artist
        sptfy_query_full = f'{sptfy_query_endpoint}/?q={search_string}&type=artist,track&limit=1'
        r = requests.get(sptfy_query_full, headers=sptfy_query_header)
        r_search_result = r.json()
        track_uri_list.append(r_search_result['tracks']['items'][0]['uri'])
    return track_uri_list

'''
The user signing into spotify earlier obtained the necessary auth code for us.
This auth code is used to get an access token for the user.
This access token will be used later to make API requests on behalf of that 
user for things like playlist creation.
'''
def get_spotify_user_access_token():
    r = requests.post(token_url, data=token_data, headers=token_header)
    r_token_data = r.json()
    valid_request = r.status_code is 200
    if not valid_request:
        raise requests.HTTPError(f'''User access token request failed with 
    HTTP error {r.status_code}.
    Expected status code 200.''')
    access_token = r_token_data['access_token']
    # expires and refresh unusued but can be used in future for refreshed api
    # access as expiry is 3600s
    expires_in = r_token_data['expires_in']
    refresh_token = r_token_data['refresh_token']
    scopes = r_token_data['scope']
    return access_token

def create_new_sptfy_playlist_with_id(access_token, playlist_name):
    sptfy_user_id = secrets['spotify_user_id']
    playlist_endpoint = f'https://api.spotify.com/v1/users/{sptfy_user_id}/playlists'
    playlist_data = {
        'name': playlist_name
    }
    playlist_header = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    playlist_data_j = json.dumps(playlist_data)
    r = requests.post(playlist_endpoint, headers=playlist_header, data=playlist_data_j)
    r_playlist_data = r.json()
    valid_request = r.status_code is 200 or 201
    if not valid_request:
        raise requests.HTTPError(f'''Playlist creation request failed with
        HTTP error {r.status_code}.
        Expected status code 200-201''')
    playlist_id = r_playlist_data['id']
    return playlist_id


def add_tracks_to_spotify_playlist(spotify_playlist_id, track_list, user_access_token):
    playlist_endpoint = f'https://api.spotify.com/v1/playlists/{spotify_playlist_id}/tracks'
    headers = {
        'Authorization': f'Bearer {user_access_token}',
        'Content-Type': 'application/json'
    }
    playlist_payload = {
        'uris': track_list
    }
    playlist_payload_j = json.dumps(playlist_payload)
    r = requests.post(playlist_endpoint, headers=headers, data=playlist_payload_j)
    valid_request = r.status_code is 200 or 201
    if not valid_request:
        raise requests.HTTPError(f'''Playlist update request failed with
        HTTP error {r.status_code}.
        Expected status code 200-201''')


if __name__ == '__main__':
    lfm_top_tracks = lfm_get_top_tracks(lfm_api_root, lfm_payload, pages, track_play_rank_lim)
    track_uri_list = get_spotify_track_uris_from(lfm_top_tracks)
    access_token = get_spotify_user_access_token()
    playlist_name = generate_playlist_name(period, date.today())
    playlist_id = create_new_sptfy_playlist_with_id(access_token, playlist_name)
    add_tracks_to_spotify_playlist(playlist_id, track_uri_list, access_token)
    print(f'Playlist was created with the name "{playlist_name}"')
