import random
import os
from collections import defaultdict

# Following three lines must be in this order or matplotlib crashes
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt


from PIL import Image, ImageDraw, ImageFont, ImageOps

import cartopy.crs as ccrs
import click
import networkx as nx
import pandas as pd

font_path = "/Users/npiccolotto/Library/Fonts/FiraCode-Light.ttf"


def subtract(x, val):
    return x - val


def subtract_abs(x, val):
    return abs(x - val)


def add(x, val):
    return x + val


def get_color_for_str(s):
    random.seed(s)
    color = [random.randint(0, 255) / 255 for i in range(3)]
    return color


def get_color_string_for_str(s):
    random.seed(s)
    r, g, b = [random.randint(0, 255) for i in range(3)]
    return f'rgb({r}, {g}, {b})'


def render_pyplot(df, dataset_args=None, render_args=None):
    from cartopy.io.img_tiles import OSM

    tiles = OSM()
    fig = plt.figure(figsize=(18, 18))
    ax = plt.axes(projection=tiles.crs)

    for route in df['route_id'].unique():
        df_route = df.loc[df['route_id'] == route]
        ax.plot(df_route.stop_lon.values,
                df_route.stop_lat.values,
                color=get_color_for_str(route),
                transform=ccrs.Geodetic(),
                markersize=2,
                marker='o')
    filename = 'pyplot_' + \
        '_'.join([dataset_args['dataset'],
                  dataset_args['agency'], dataset_args['route']])
    plt.savefig(f'{filename}.png')


def draw_nx_graph(G, render_args=None):
    if render_args == None:
        render_args = default_dict(False)
    src_crs = ccrs.Geodetic()
    dst_crs = ccrs.Mercator()
    cartesian_points = {}
    resolution = 1 / render_args['render_resolution']  # px/m
    for node in G.nodes(data=True):
        node_id, attrs = node
        x, y = dst_crs.transform_point(
            attrs['lon'], attrs['lat'], src_crs=src_crs)
        cartesian_points[node_id] = [
            attrs['name'],
            int(x * resolution),
            int(y * resolution)
        ]

    df = pd.DataFrame.from_dict(
        cartesian_points, orient='index', columns=['name', 'x', 'y'])

    # more x = more east, if we centered on the westmost point
    east = df.x.min()
    west = df.x.max()
    # more y = more north
    north = df.y.max()
    south = df.y.min()

    df.x = df.x.apply(subtract, args=(east,))
    df.y = df.y.apply(subtract_abs, args=(north,))

    margin = int(8_000 * resolution)

    df.x = df.x.apply(add, args=(margin,))
    df.y = df.y.apply(add, args=(margin,))

    img = Image.new('RGB', [abs(west - east + 2 * margin),
                            abs(north - south + 2 * margin)], color='white')
    draw = ImageDraw.Draw(img)
    marker_size = int(resolution * 100)
    line_width = int(marker_size / 2)

    for u_id, v_id, attrs in G.edges(data=True):
        route = attrs['route']
        color = get_color_string_for_str(route)
        u = df.loc[u_id]
        v = df.loc[v_id]
        draw.line([u.x, u.y, v.x, v.y], fill=color, width=line_width)

    font_size = int(resolution * 300)
    font = ImageFont.truetype(font_path, font_size)
    for name, x, y in df.values:
        draw.ellipse([x - marker_size, y - marker_size,
                      x + marker_size, y + marker_size], fill='white', outline='black', width=line_width)
        if render_args['render_stop_names']:
            """ txt = Image.new('L', (500, font_size))
            d = ImageDraw.Draw(txt)
            d.text((0, 0), name, font=font, fill=255)
            w = txt.rotate(17.5, expand=1)
            img.paste(ImageOps.colorize(
                w, (0, 0, 0), (0, 0, 0)), (x, y), w) """
            draw.text([x + 2 * marker_size, y - 2 * marker_size],
                      name, fill='black', font=font)
    return img


def render_custom(df, dataset_args=None, **kwargs):
    G = nx.Graph()  # TODO use multigraph for routes that share stops

    for route in df['route_id'].unique():
        df_route = df.loc[df['route_id'] == route]
        df_route = df_route.sort_values(['stop_sequence'])
        for stop in df_route.values:
            agency_id, agency_name, route_id, route_short_name, stop_nr, stop_id, stop_name, stop_lat, stop_lon = stop
            G.add_node(stop_id,
                       name=stop_name,
                       lat=stop_lat,
                       lon=stop_lon)
        stops = df_route['stop_id'].values
        next_stops = stops[1:]
        for start, end in zip(stops, next_stops):
            G.add_edge(start, end, route=route)

    img = draw_nx_graph(G, **kwargs)
    filename = 'custom_' + \
        '_'.join([dataset_args['dataset'],
                  dataset_args['agency'], dataset_args['route']])
    img.save(f'{filename}.png')


@click.command()
@click.argument('dataset')
@click.option('--agency', default=None, help='1 S-Bahn, 796 BVG', type=int)
@click.option('--route', default=None, help='Route name', type=str)
@click.option('--render-stop-names', is_flag=True, default=False)
@click.option('--render-resolution', help='How many meters equals one pixel', type=int, default=10)
def render(dataset, agency, route, render_stop_names, render_resolution):
    csv_file_path = f'data/{dataset}/processed.csv'
    df = pd.read_csv(csv_file_path, sep=',')

    if agency is not None:
        df = df.loc[df['agency_id'] == agency]
    if route is not None:
        df = df.loc[df['route_short_name'] == route]

    dataset_args = {
        'dataset': str(dataset),
        'agency': str(agency),
        'route': str(route)
    }

    render_args = {
        'render_stop_names': render_stop_names,
        'render_resolution': render_resolution
    }

    render_pyplot(df, dataset_args=dataset_args, render_args=render_args)
    render_custom(df, dataset_args=dataset_args, render_args=render_args)


if __name__ == '__main__':
    render()
